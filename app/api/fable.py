"""POST /fable/generate-pdf — 원문→채점→PDF 바이너리."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.fable_pdf.service import FablePdfService, get_fable_pdf_service
from app.schemas.fable import FableGeneratePdfRequest

router = APIRouter(tags=["fable"])


@router.post("/fable/generate-pdf")
def generate_fable_pdf_endpoint(
    body: FableGeneratePdfRequest,
    service: FablePdfService = Depends(get_fable_pdf_service),
) -> Response:
    """원문을 Groq 채점 후 PDF 바이너리로 반환한다. ID는 서버 채번."""
    text = (body.body_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="원문(body_text)이 비어 있습니다.")

    try:
        result = service(text, body.source_note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"채점에 실패했습니다. 시간 초과입니다. 다시 시도해 주세요. ({exc})",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — API 경계 안내
        raise HTTPException(
            status_code=502,
            detail=f"채점에 실패했습니다. 다시 시도해 주세요. ({exc})",
        ) from exc

    # 한글 제목은 ISO-8859-1 헤더 제약이 있어 percent-encoding
    headers = {
        "X-Fable-Id": str(result.fable_id),
        "X-Fable-Title": quote(result.title or "", safe=""),
        "X-Fable-Subtitle": quote(result.subtitle or "", safe=""),
        "Content-Disposition": f'attachment; filename="fable_{result.fable_id}.pdf"',
    }
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )
