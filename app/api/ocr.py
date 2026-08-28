"""POST /ocr/turn · POST /ocr/session/clear · GET /ocr/pdf — 판단은 TurnService만."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.config import get_settings
from app.graph.ocr.service import OcrGraphTurnService, get_ocr_graph_turn_service
from app.ocr.pdf import build_receipt_pdf_bytes
from app.ocr.session import default_ocr_store
from app.ocr.turn import OcrTurnService, get_ocr_turn_service
from app.schemas.ocr import OcrClearRequest, OcrTurnRequest, OcrTurnResponse

router = APIRouter(tags=["ocr"])


def _use_graph() -> bool:
    """3-1/3-2: 그래프 경로 스위치. 기본값은 레거시 유지, 명시적으로 켰을 때만 그래프.

    .env(OCR_USE_GRAPH=1)/OS 환경변수 둘 다 반영된다 — get_settings()가
    pydantic_settings로 두 출처를 이미 병합해서 읽어준다(OS 환경변수가 .env보다 우선).
    """
    return get_settings().ocr_use_graph


def _actor(request: Request) -> str:
    return request.headers.get("X-Admin-User-Id", "guest")


def _log(
    *,
    event: str,
    api: str,
    admin_user_id: str,
    session_id: str | None,
    result: str,
    reason: str | None = None,
) -> None:
    lines = [
        f"[{datetime.now(timezone.utc).isoformat()}] event={event}",
        f"  api={api}",
        f"  admin_user_id={(admin_user_id or 'guest').strip() or 'guest'}",
        f"  session_id={(session_id or '-').strip() or '-'}",
        f"  result={result}",
    ]
    if reason:
        lines.append(f"  reason={reason}")
    print("\n".join(lines), flush=True)


def _to_response(result) -> OcrTurnResponse:
    return OcrTurnResponse(
        reply=result.reply,
        lines=result.lines,
        total=result.total,
        kinds_selectable=result.kinds_selectable,
        kind_id=result.kind_id,
        preview_ready=result.preview_ready,
        preview_opened=result.preview_opened,
        unread=result.unread,
        action_enabled=result.action_enabled,
        kinds=result.kinds,
        raw_text=getattr(result, "raw_text", "") or "",
        unclear_lines=getattr(result, "unclear_lines", None) or [],
        prior_reply=getattr(result, "prior_reply", "") or "",
    )


@router.post("/ocr/turn", response_model=OcrTurnResponse)
def ocr_turn(
    body: OcrTurnRequest,
    request: Request,
    service: OcrTurnService = Depends(get_ocr_turn_service),
    graph_service: OcrGraphTurnService = Depends(get_ocr_graph_turn_service),
) -> OcrTurnResponse:
    admin_user_id = _actor(request)
    active_service = graph_service if _use_graph() else service
    _log(
        event="OCR 턴",
        api="POST /ocr/turn",
        admin_user_id=admin_user_id,
        session_id=body.session_id,
        result="requested",
    )
    try:
        result = active_service.handle(
            session_id=body.session_id,
            text=body.text,
            image_base64=body.image_base64,
            filename=body.filename,
            mime=body.mime,
            action=body.action,
            kind_id=body.kind_id,
        )
    except Exception as exc:  # noqa: BLE001
        _log(
            event="OCR 턴",
            api="POST /ocr/turn",
            admin_user_id=admin_user_id,
            session_id=body.session_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"OCR 처리 실패: {exc}") from exc
    _log(
        event="OCR 턴",
        api="POST /ocr/turn",
        admin_user_id=admin_user_id,
        session_id=body.session_id,
        result="success",
    )
    return _to_response(result)


@router.post("/ocr/session/clear", response_model=OcrTurnResponse)
def ocr_session_clear(
    body: OcrClearRequest,
    request: Request,
    service: OcrTurnService = Depends(get_ocr_turn_service),
) -> OcrTurnResponse:
    admin_user_id = _actor(request)
    _log(
        event="OCR 세션 클리어",
        api="POST /ocr/session/clear",
        admin_user_id=admin_user_id,
        session_id=body.session_id,
        result="requested",
    )
    result = service.clear(body.session_id)
    _log(
        event="OCR 세션 클리어",
        api="POST /ocr/session/clear",
        admin_user_id=admin_user_id,
        session_id=body.session_id,
        result="success",
    )
    return _to_response(result)


@router.get("/ocr/pdf")
def ocr_pdf(
    request: Request,
    session_id: str = "",
) -> Response:
    admin_user_id = _actor(request)
    _log(
        event="OCR PDF 다운로드",
        api="GET /ocr/pdf",
        admin_user_id=admin_user_id,
        session_id=session_id,
        result="requested",
    )
    state = default_ocr_store.get(session_id)
    if not state.lines:
        _log(
            event="OCR PDF 다운로드",
            api="GET /ocr/pdf",
            admin_user_id=admin_user_id,
            session_id=session_id,
            result="failure",
            reason="품목이 없습니다.",
        )
        raise HTTPException(status_code=400, detail="품목이 없습니다.")
    pdf_bytes = build_receipt_pdf_bytes(state.lines, state.kind_id)
    filename = quote("영수증_2연.pdf")
    _log(
        event="OCR PDF 다운로드",
        api="GET /ocr/pdf",
        admin_user_id=admin_user_id,
        session_id=session_id,
        result="success",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
