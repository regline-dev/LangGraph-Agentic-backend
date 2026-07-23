"""POST /pdf/inspect · POST /pdf/ingest — PDF 검사·적재."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.pdf_ingest.service import PdfIngestService, get_pdf_ingest_service
from app.schemas.pdf_ingest import PdfIngestResponse, PdfInspectResponse

router = APIRouter(tags=["pdf-ingest"])


def _is_non_pdf_filename(filename: str) -> bool:
    """확장자가 .pdf가 아니면 True."""
    name = Path(filename or "").name
    return not name or Path(name).suffix.lower() != ".pdf"


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
    file: UploadFile = File(...),
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfInspectResponse:
    """적재 없이 우화 카드 여부·기본/특화 메타만 반환."""
    filename, content = await _read_pdf_upload(file)
    try:
        result = service.inspect(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"PDF 검사에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    return PdfInspectResponse(
        is_fable_card=result.is_fable_card,
        page_count=result.page_count,
        basic_metadata=result.basic_metadata,
        fable_metadata=result.fable_metadata,
    )


@router.post("/pdf/ingest", response_model=PdfIngestResponse)
async def ingest_pdf_endpoint(
    file: UploadFile = File(...),
    service: PdfIngestService = Depends(get_pdf_ingest_service),
) -> PdfIngestResponse:
    """어드민 PDF 벡터화 — FAQ 엑셀 경로와 분리."""
    filename, content = await _read_pdf_upload(file)

    try:
        result = service(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — API 경계 안내
        raise HTTPException(
            status_code=502,
            detail=f"벡터화에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    return PdfIngestResponse(
        source_file=result.source_file,
        indexed=result.indexed,
        collection=result.collection,
        page_count=result.page_count,
        metadata=result.metadata,
        basic_metadata=result.basic_metadata,
        is_fable_card=result.is_fable_card,
    )
