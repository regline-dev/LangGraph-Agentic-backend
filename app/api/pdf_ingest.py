"""POST /pdf/inspect · /pdf/ingest · /pdf/templates."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile

from app.pdf_ingest.api_log import log_pdf_api
from app.pdf_ingest.service import PdfIngestService, get_pdf_ingest_service
from app.schemas.pdf_ingest import (
    PdfDeleteTemplateResponse,
    PdfIngestResponse,
    PdfInspectResponse,
    PdfSaveTemplateRequest,
    PdfSaveTemplateResponse,
    PdfTemplateListItem,
    PdfTemplateListResponse,
)

router = APIRouter(tags=["pdf-ingest"])


def _admin_user_id(request: Request) -> str:
    return request.headers.get("X-Admin-User-Id", "guest")


def _is_non_pdf_filename(filename: str) -> bool:
    """확장자가 .pdf가 아니면 True."""
    name = Path(filename or "").name
    return not name or Path(name).suffix.lower() != ".pdf"


def _normalize_prompt(prompt: str | None) -> str | None:
    """빈 문자열은 None으로 통일."""
    if prompt is None:
        return None
    text = str(prompt).strip()
    return text or None


async def _read_pdf_upload(file: UploadFile) -> tuple[str, bytes]:
    filename = file.filename or ""
    if _is_non_pdf_filename(filename):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")
    try:
        content = await file.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"파일을 읽을 수 없습니다. ({exc})") from exc
    return filename, content


@router.post("/pdf/inspect", response_model=PdfInspectResponse)
async def inspect_pdf_endpoint(
    request: Request,
    file: UploadFile = File(...),
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfInspectResponse:
    """적재 없이 메타·지문·템플릿 매칭 반환."""
    admin_user_id = _admin_user_id(request)
    log_pdf_api(
        api="POST /pdf/inspect",
        admin_user_id=admin_user_id,
        result="received",
    )
    try:
        filename, content = await _read_pdf_upload(file)
        result = service.inspect(filename, content)
    except HTTPException as exc:
        log_pdf_api(
            api="POST /pdf/inspect",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc.detail),
        )
        raise
    except ValueError as exc:
        log_pdf_api(
            api="POST /pdf/inspect",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log_pdf_api(
            api="POST /pdf/inspect",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=f"PDF 검사에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    response = PdfInspectResponse(
        is_fable_card=result.is_fable_card,
        page_count=result.page_count,
        basic_metadata=result.basic_metadata,
        fable_metadata=result.fable_metadata,
        document_kind=result.document_kind,
        structure_labels=list(result.structure_labels or []),
        extracted_metadata=list(result.extracted_metadata or []),
        template_match_status=result.template_match_status,
        template_id=result.template_id,
        template_prompt=result.template_prompt,
        prompt_locked=bool(result.prompt_locked),
        template_candidates=list(result.template_candidates or []),
        text_excerpt=result.text_excerpt or "",
        result_schema=result.result_schema,
        filled_result=result.filled_result,
        document_version_preview_action=result.document_version_preview_action,
        document_id=result.document_id,
        content_hash=result.content_hash,
    )
    extracted_count = len(result.extracted_metadata or [])
    log_pdf_api(
        api="POST /pdf/inspect",
        admin_user_id=admin_user_id,
        template_id=result.template_id,
        result="success",
        reason=(
            "추천 메타데이터 후보 없음(extracted_metadata=0)"
            if extracted_count == 0
            else None
        ),
    )
    return response


@router.get("/pdf/templates", response_model=PdfTemplateListResponse)
async def list_templates_endpoint(
    request: Request,
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfTemplateListResponse:
    """저장된 메타데이터 템플릿 목록."""
    admin_user_id = _admin_user_id(request)
    log_pdf_api(
        api="GET /pdf/templates",
        admin_user_id=admin_user_id,
        result="received",
    )
    try:
        rows = service.list_prompt_templates()
    except Exception as exc:  # noqa: BLE001
        log_pdf_api(
            api="GET /pdf/templates",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc),
        )
        raise
    response = PdfTemplateListResponse(
        templates=[PdfTemplateListItem(**row) for row in rows]
    )
    log_pdf_api(
        api="GET /pdf/templates",
        admin_user_id=admin_user_id,
        result="success",
    )
    return response


@router.post("/pdf/templates", response_model=PdfSaveTemplateResponse)
async def save_template_endpoint(
    request: Request,
    body: PdfSaveTemplateRequest,
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfSaveTemplateResponse:
    """판별용 labels + 결과 양식(또는 탐색 지시문) 저장."""
    from app.pdf_ingest.template_store import has_result_schema

    admin_user_id = _admin_user_id(request)
    log_pdf_api(
        api="POST /pdf/templates",
        admin_user_id=admin_user_id,
        template_id=body.template_id,
        result="received",
    )
    try:
        saved = service.save_prompt_template(
            template_id=body.template_id,
            name=body.name,
            labels=list(body.labels or []),
            prompt=body.prompt or "",
            result_schema=body.result_schema,
        )
    except ValueError as exc:
        log_pdf_api(
            api="POST /pdf/templates",
            admin_user_id=admin_user_id,
            template_id=body.template_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log_pdf_api(
            api="POST /pdf/templates",
            admin_user_id=admin_user_id,
            template_id=body.template_id,
            result="failure",
            reason=str(exc),
        )
        raise
    response = PdfSaveTemplateResponse(
        template_id=saved.template_id,
        name=saved.name,
        labels=sorted(saved.labels),
        saved=True,
        has_result_schema=has_result_schema(saved),
    )
    log_pdf_api(
        api="POST /pdf/templates",
        admin_user_id=admin_user_id,
        template_id=saved.template_id,
        result="success",
    )
    return response


@router.delete("/pdf/templates/{template_id}", response_model=PdfDeleteTemplateResponse)
async def delete_template_endpoint(
    request: Request,
    template_id: str,
    delete_vectors: bool = Query(False),
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfDeleteTemplateResponse:
    """템플릿 soft-delete. delete_vectors=true 이면 template_id 벡터도 삭제."""
    admin_user_id = _admin_user_id(request)
    log_pdf_api(
        api="DELETE /pdf/templates/{template_id}",
        admin_user_id=admin_user_id,
        template_id=template_id,
        result="received",
    )
    try:
        result = service.delete_prompt_template(
            template_id=template_id,
            delete_vectors=delete_vectors,
        )
    except FileNotFoundError as exc:
        log_pdf_api(
            api="DELETE /pdf/templates/{template_id}",
            admin_user_id=admin_user_id,
            template_id=template_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        log_pdf_api(
            api="DELETE /pdf/templates/{template_id}",
            admin_user_id=admin_user_id,
            template_id=template_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log_pdf_api(
            api="DELETE /pdf/templates/{template_id}",
            admin_user_id=admin_user_id,
            template_id=template_id,
            result="failure",
            reason=str(exc),
        )
        raise
    response = PdfDeleteTemplateResponse(**result)
    log_pdf_api(
        api="DELETE /pdf/templates/{template_id}",
        admin_user_id=admin_user_id,
        template_id=template_id,
        result="success",
    )
    return response


@router.post("/pdf/ingest", response_model=PdfIngestResponse)
async def ingest_pdf_endpoint(
    request: Request,
    file: UploadFile = File(...),
    prompt: str | None = Form(None),
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfIngestResponse:
    """어드민 PDF 벡터화 — file + 선택적 prompt(메타데이터 관련)."""
    admin_user_id = _admin_user_id(request)
    log_pdf_api(
        api="POST /pdf/ingest",
        admin_user_id=admin_user_id,
        result="received",
    )
    try:
        filename, content = await _read_pdf_upload(file)
        normalized_prompt = _normalize_prompt(prompt)
        result = service(filename, content, prompt=normalized_prompt)
    except HTTPException as exc:
        log_pdf_api(
            api="POST /pdf/ingest",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc.detail),
        )
        raise
    except ValueError as exc:
        log_pdf_api(
            api="POST /pdf/ingest",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log_pdf_api(
            api="POST /pdf/ingest",
            admin_user_id=admin_user_id,
            result="failure",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=f"벡터화에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    response = PdfIngestResponse(
        source_file=result.source_file,
        indexed=result.indexed,
        collection=result.collection,
        page_count=result.page_count,
        metadata=result.metadata,
        basic_metadata=result.basic_metadata,
        is_fable_card=result.is_fable_card,
        document_version_action=result.document_version_action,
        document_id=result.document_id,
        version=result.version,
        content_hash=result.content_hash,
    )
    log_pdf_api(
        api="POST /pdf/ingest",
        admin_user_id=admin_user_id,
        template_id=result.basic_metadata.get("template_id"),
        result="success",
    )
    return response
