"""POST /fable/generate-pdf — 원문→채점→PDF 바이너리.
POST /fable/draft-configs — 커스텀 구성 초안(LLM 1회).
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.fable_pdf import typed_scorer
from app.fable_pdf.pdf_type_profile import is_aesop_type, profile_from_request
from app.fable_pdf.scorer import score_fable_with_llm
from app.fable_pdf.service import FablePdfService, get_fable_pdf_service
from app.schemas.fable import (
    FableDraftConfigsRequest,
    FableGeneratePdfRequest,
    FablePreviewLlmRequest,
)

router = APIRouter(tags=["fable"])


def _admin_user_id(request: Request) -> str:
    return request.headers.get("X-Admin-User-Id", "guest")


def _log_fable(
    *,
    event: str,
    api: str,
    admin_user_id: str,
    type_code: str | None,
    result: str,
    reason: str | None = None,
) -> None:
    lines = [
        f"[{datetime.now(timezone.utc).isoformat()}] event={event}",
        f"  api={api}",
        f"  admin_user_id={(admin_user_id or 'guest').strip() or 'guest'}",
        f"  type_code={(type_code or '-').strip() or '-'}",
        f"  result={result}",
    ]
    if reason:
        lines.append(f"  reason={reason}")
    print("\n".join(lines), flush=True)


@router.post("/fable/generate-pdf")
def generate_fable_pdf_endpoint(
    body: FableGeneratePdfRequest,
    request: Request,
    service: FablePdfService = Depends(get_fable_pdf_service),
) -> Response:
    """원문을 채점 후 PDF 바이너리로 반환. 타입에 따라 이솝/구성 기반 분기."""
    admin_user_id = _admin_user_id(request)
    type_code = body.type_code or "-"
    text = (body.body_text or "").strip()
    if not text:
        _log_fable(
            event="PDF 생성",
            api="POST /fable/generate-pdf",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason="원문(body_text)이 비어 있습니다.",
        )
        raise HTTPException(status_code=400, detail="원문(body_text)이 비어 있습니다.")

    _log_fable(
        event="PDF 생성",
        api="POST /fable/generate-pdf",
        admin_user_id=admin_user_id,
        type_code=type_code,
        result="requested",
    )

    type_profile = profile_from_request(
        type_code=body.type_code,
        type_name=body.type_name,
        configs=[c.model_dump() for c in body.configs] if body.configs else None,
        subtitles=[s.model_dump() for s in body.subtitles] if body.subtitles else None,
        type_updated_at=body.type_updated_at,
        type_updated_by=body.type_updated_by,
    )

    try:
        try:
            result = service(
                text,
                body.source_note,
                type_profile,
                preview_score=body.preview_score,
            )
        except TypeError:
            try:
                result = service(text, body.source_note, type_profile)
            except TypeError:
                # 테스트 더블·구시그니처 호환
                result = service(text, body.source_note)
    except ValueError as exc:
        _log_fable(
            event="PDF 생성",
            api="POST /fable/generate-pdf",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        _log_fable(
            event="PDF 생성",
            api="POST /fable/generate-pdf",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason=f"시간 초과: {exc}",
        )
        raise HTTPException(
            status_code=502,
            detail=f"채점에 실패했습니다. 시간 초과입니다. 다시 시도해 주세요. ({exc})",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — API 경계 안내
        _log_fable(
            event="PDF 생성",
            api="POST /fable/generate-pdf",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=f"채점에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    _log_fable(
        event="PDF 생성",
        api="POST /fable/generate-pdf",
        admin_user_id=admin_user_id,
        type_code=type_code,
        result="success",
    )
    headers = {
        "X-Fable-Id": str(result.fable_id),
        "X-Fable-Title": quote(result.title or "", safe=""),
        "Content-Disposition": f'attachment; filename="fable_{result.fable_id}.pdf"',
    }
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )


@router.post("/fable/draft-configs")
def draft_fable_configs_endpoint(
    body: FableDraftConfigsRequest,
    request: Request,
) -> dict:
    """커스텀만: 원문에서 항목·값·차트를 LLM 한 번에 뽑는다. 이솝은 거절."""
    admin_user_id = _admin_user_id(request)
    type_code = body.type_code or "-"
    text = (body.body_text or "").strip()
    if not text:
        _log_fable(
            event="PDF 구성 초안",
            api="POST /fable/draft-configs",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason="원문(body_text)이 비어 있습니다.",
        )
        raise HTTPException(status_code=400, detail="원문(body_text)이 비어 있습니다.")

    type_profile = profile_from_request(
        type_code=body.type_code,
        type_name=body.type_name,
        configs=None,
        subtitles=None,
    )
    if type_profile is not None and is_aesop_type(type_profile):
        _log_fable(
            event="PDF 구성 초안",
            api="POST /fable/draft-configs",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason="이솝 타입은 구성 초안을 사용하지 않습니다.",
        )
        raise HTTPException(
            status_code=400,
            detail="이솝 타입은 구성 초안을 사용하지 않습니다.",
        )

    _log_fable(
        event="PDF 구성 초안",
        api="POST /fable/draft-configs",
        admin_user_id=admin_user_id,
        type_code=type_code,
        result="requested",
    )
    try:
        drafted = typed_scorer.draft_typed_items_with_llm(
            text, (body.type_name or "").strip()
        )
        drafted = typed_scorer.overlay_colon_labeled_draft(text, drafted)
    except Exception as exc:  # noqa: BLE001 — API 경계 안내
        _log_fable(
            event="PDF 구성 초안",
            api="POST /fable/draft-configs",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=f"구성 초안에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    _log_fable(
        event="PDF 구성 초안",
        api="POST /fable/draft-configs",
        admin_user_id=admin_user_id,
        type_code=type_code,
        result="success",
    )
    return {
        "title": drafted.get("title") or "",
        "items": drafted.get("items") or [],
        "tags": drafted.get("tags") or [],
    }


def _groups_to_preview_items(groups: dict) -> list[dict]:
    """미리보기 화면용 — 그룹명과 값 한 줄. 새 항목 이름은 만들지 않는다."""
    items: list[dict] = []
    if not isinstance(groups, dict):
        return items
    for group_name, fields in groups.items():
        if not str(group_name or "").strip():
            continue
        if not isinstance(fields, dict):
            items.append(
                {"name": str(group_name), "value": str(fields or ""), "chart": "none"}
            )
            continue
        summary = str(fields.get("요약") or "").strip()
        if summary:
            value = summary
        else:
            value = " ".join(
                str(part).strip()
                for key, part in fields.items()
                if str(key) != "요약" and str(part).strip()
            )
        items.append({"name": str(group_name), "value": value, "chart": "none"})
    return items


@router.post("/fable/preview-llm")
def preview_fable_llm_endpoint(
    body: FablePreviewLlmRequest,
    request: Request,
) -> dict:
    """미리보기 LLM. 이솝=채점. 커스텀=보낸 구성 이름에 값만."""
    admin_user_id = _admin_user_id(request)
    type_code = body.type_code or "-"
    text = (body.body_text or "").strip()
    if not text:
        _log_fable(
            event="PDF 미리보기 LLM",
            api="POST /fable/preview-llm",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason="원문(body_text)이 비어 있습니다.",
        )
        raise HTTPException(status_code=400, detail="원문(body_text)이 비어 있습니다.")

    config_payload = None
    if body.configs:
        config_payload = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in body.configs
        ]
    subtitle_payload = None
    if body.subtitles:
        subtitle_payload = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in body.subtitles
        ]
    type_profile = profile_from_request(
        type_code=body.type_code,
        type_name=body.type_name,
        configs=config_payload,
        subtitles=subtitle_payload,
    )
    _log_fable(
        event="PDF 미리보기 LLM",
        api="POST /fable/preview-llm",
        admin_user_id=admin_user_id,
        type_code=type_code,
        result="requested",
    )
    try:
        if type_profile is None or is_aesop_type(type_profile):
            scored = score_fable_with_llm(text)
            _log_fable(
                event="PDF 미리보기 LLM",
                api="POST /fable/preview-llm",
                admin_user_id=admin_user_id,
                type_code=type_code,
                result="success",
            )
            return {
                "mode": "aesop",
                "title": scored.get("title") or "",
                "items": [],
                "score": scored,
            }
        named_configs = [
            cfg
            for cfg in (type_profile.configs or [])
            if str(cfg.get("group_name") or "").strip()
        ]
        named_subtitles = [
            item
            for item in (type_profile.subtitles or [])
            if str(item.get("title") or "").strip()
        ]
        if not named_configs and not named_subtitles:
            _log_fable(
                event="PDF 미리보기 LLM",
                api="POST /fable/preview-llm",
                admin_user_id=admin_user_id,
                type_code=type_code,
                result="success",
            )
            return {
                "mode": "custom",
                "title": "",
                "items": [],
                "groups": {},
                "subtitles": {},
                "score": None,
                "tags": [],
            }
        scored = typed_scorer.score_typed_with_llm(text, type_profile)
    except Exception as exc:  # noqa: BLE001 — API 경계 안내
        _log_fable(
            event="PDF 미리보기 LLM",
            api="POST /fable/preview-llm",
            admin_user_id=admin_user_id,
            type_code=type_code,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=f"미리보기 채점에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    groups = scored.get("groups") if isinstance(scored.get("groups"), dict) else {}
    subtitles = (
        scored.get("subtitles") if isinstance(scored.get("subtitles"), dict) else {}
    )
    _log_fable(
        event="PDF 미리보기 LLM",
        api="POST /fable/preview-llm",
        admin_user_id=admin_user_id,
        type_code=type_code,
        result="success",
    )
    return {
        "mode": "custom",
        "title": scored.get("title") or "",
        "items": _groups_to_preview_items(groups),
        "groups": groups,
        "subtitles": subtitles,
        "score": None,
        "tags": scored.get("tags") or [],
    }
