"""PDF 상단 헤더 포맷 TDD."""

from __future__ import annotations

from app.fable_pdf.pdf_header import (
    build_top_header_left,
    format_document_created_date,
    format_type_updated_stamp,
)


def test_format_type_updated_stamp_from_datetime_string() -> None:
    assert format_type_updated_stamp("2026-08-08 12:03:00") == "202608081203"
    assert format_type_updated_stamp("2026-08-08T12:03:00") == "202608081203"


def test_build_top_header_left_layout() -> None:
    text = build_top_header_left(
        metadata_name="ABCD",
        type_updated_at="2026-08-08 12:03:00",
        type_updated_by="counsel1",
    )
    assert text.startswith("METADATA_NAME: ABCD")
    assert "    " in text
    assert "PDF 타입 수정일 : 202608081203 / counsel1" in text


def test_format_document_created_date() -> None:
    assert format_document_created_date("2026-08-08") == "2026-08-08"
    assert format_document_created_date("2026-08-08 12:00:00") == "2026-08-08"
