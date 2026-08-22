"""METADATA_NAME(=type_code) PDF 스탬프 TDD."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.fable_pdf.metadata_stamp import (
    normalize_type_code,
    stamp_metadata_name_on_pdf,
    validate_type_code,
)
from app.fable_pdf.pdf_generator import generate_fable_pdf
from app.fable_pdf.typed_pdf import generate_typed_pdf


def _blank_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "sample")
    c.save()


def test_normalize_type_code_strips_and_upper() -> None:
    assert normalize_type_code("  local_festival ") == "LOCAL_FESTIVAL"
    assert normalize_type_code("aesop") == "AESOP"


def test_validate_type_code_rejects_empty_and_timestamp_style() -> None:
    assert validate_type_code("").ok is False
    assert validate_type_code("type_1786160352760").ok is False
    assert validate_type_code("local_festival").ok is True
    assert validate_type_code("local_festival").code == "LOCAL_FESTIVAL"


def test_stamp_writes_metadata_name_into_pdf_info(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    _blank_pdf(path)
    stamp_metadata_name_on_pdf(str(path), "local_festival")
    reader = PdfReader(str(path))
    meta = reader.metadata
    assert meta is not None
    # pypdf may expose custom keys via get
    raw = None
    if hasattr(meta, "get"):
        raw = meta.get("/METADATA_NAME")
    assert raw is not None
    assert "LOCAL_FESTIVAL" in str(raw)


def test_typed_pdf_includes_metadata_name_text_line(tmp_path: Path) -> None:
    """상단에 METADATA_NAME · 타입 수정일 · 문서생성일이 있다."""
    out = tmp_path / "festival.pdf"
    generate_typed_pdf(
        {
            "id": 1,
            "title": "한강별빛축제",
            "body_text": "본문",
            "source_note": "테스트",
            "type_name": "지방축제 안내",
            "type_code": "local_festival",
            "type_updated_at": "2026-08-08 12:03:00",
            "type_updated_by": "counsel1",
            "document_created_date": "2026-08-08",
            "groups": {"기본 정보": {"축제명": "한강별빛축제"}},
            "group_layouts": {},
            "subtitles": {},
            "tags": [],
        },
        str(out),
    )
    stamp_metadata_name_on_pdf(str(out), "local_festival")
    from pypdf import PdfReader

    text = "".join((page.extract_text() or "") for page in PdfReader(str(out)).pages)
    compact = text.replace(" ", "")
    assert "METADATA_NAME" in compact
    assert "LOCAL_FESTIVAL" in compact
    assert "문서생성일" in compact
    assert "202608081203" in compact or "2026-08-08" in text
