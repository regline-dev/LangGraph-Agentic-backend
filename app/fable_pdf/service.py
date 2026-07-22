"""우화 PDF 생성 오케스트레이션 — 채번·tmp·파이프라인·즉시삭제."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, Protocol

from app.fable_pdf.id_sequence import next_fable_id
from app.fable_pdf.pipeline import SOURCE_NOTE_DEFAULT, run_fable_pipeline
from app.fable_pdf.tmp_store import cleanup_expired_tmp_pdfs, make_tmp_pdf_path

# 프로젝트 루트 기준 (uvicorn cwd = /app 또는 레포 루트)
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEQ_PATH = _BACKEND_ROOT / "data" / "fable_id_seq.txt"
DEFAULT_TMP_DIR = _BACKEND_ROOT / "data" / "tmp" / "fable_pdf"
FABLE_LLM_TIMEOUT_SECONDS = 100.0
TMP_TTL_SECONDS = 24 * 3600


@dataclass(frozen=True)
class FableGenerateResult:
    """API가 PDF 응답으로 바꿀 성공 결과."""

    fable_id: int
    title: str
    subtitle: str
    pdf_bytes: bytes


class FablePdfService(Protocol):
    def __call__(
        self,
        body_text: str,
        source_note: str | None = None,
    ) -> FableGenerateResult: ...


def generate_fable_pdf_bytes(
    body_text: str,
    source_note: str | None = None,
    *,
    seq_path: Path | None = None,
    tmp_dir: Path | None = None,
    timeout_seconds: float | None = None,
    pipeline_fn: Callable[..., dict] | None = None,
) -> FableGenerateResult:
    """
    1) TTL 청소 2) ID 채번 3) tmp PDF 생성 4) 바이트 읽기 5) tmp 삭제.
    """
    text = (body_text or "").strip()
    if not text:
        raise ValueError("원문(body_text)이 비어 있습니다.")

    seq = Path(seq_path or DEFAULT_SEQ_PATH)
    out_dir = Path(tmp_dir or DEFAULT_TMP_DIR)
    timeout = FABLE_LLM_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    note = (source_note or "").strip() or SOURCE_NOTE_DEFAULT

    if pipeline_fn is None:
        # 실파이프라인에 LLM 한도(기본 100초)를 고정
        pipeline: Callable[..., dict] = partial(
            run_fable_pipeline,
            timeout_seconds=timeout,
        )
    else:
        pipeline = pipeline_fn

    cleanup_expired_tmp_pdfs(tmp_dir=out_dir, ttl_seconds=TMP_TTL_SECONDS)
    fable_id = next_fable_id(seq)
    pdf_path = make_tmp_pdf_path(tmp_dir=out_dir, fable_id=fable_id)

    meta: dict = {}
    pdf_bytes = b""
    try:
        meta = pipeline(text, fable_id, str(pdf_path), note)
        if not pdf_path.is_file():
            raise RuntimeError("PDF 파일이 생성되지 않았습니다.")
        pdf_bytes = pdf_path.read_bytes()
        if not pdf_bytes:
            raise RuntimeError("생성된 PDF가 비어 있습니다.")
    finally:
        try:
            pdf_path.unlink(missing_ok=True)
        except OSError:
            pass

    return FableGenerateResult(
        fable_id=fable_id,
        title=str((meta or {}).get("title") or ""),
        subtitle=str((meta or {}).get("subtitle") or ""),
        pdf_bytes=pdf_bytes,
    )


def get_fable_pdf_service() -> FablePdfService:
    """FastAPI Depends용 — 기본 실서비스."""
    return generate_fable_pdf_bytes
