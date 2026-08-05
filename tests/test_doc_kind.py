"""문서 특성 판별 — find_tables·행수 · 3은 미개발 아님."""

from pathlib import Path

import pytest

from app.pdf_ingest.doc_kind import (
    DOC_KIND_GENERAL_TEXT,
    DOC_KIND_SCAN_IMAGE,
    DOC_KIND_TABLE,
    classify_document_kind,
    undeveloped_message,
)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"


def test_plain_prose_is_general_text() -> None:
    text = "춘향은 이몽룡과 백년가약을 맺었다.\n" * 5
    assert classify_document_kind(page_count=1, text=text) == DOC_KIND_GENERAL_TEXT
    assert undeveloped_message(DOC_KIND_GENERAL_TEXT) is None


def test_little_text_many_pages_is_scan() -> None:
    assert classify_document_kind(page_count=5, text="ab") == DOC_KIND_SCAN_IMAGE
    assert "스캔본/이미지" in (undeveloped_message(DOC_KIND_SCAN_IMAGE) or "")


def test_table_kind_is_not_undeveloped() -> None:
    assert undeveloped_message(DOC_KIND_TABLE) is None


def test_pipe_text_alone_is_not_table_without_pdf() -> None:
    """'|' 휴리스틱 제거 — 경로 없으면 표로 단정하지 않음."""
    text = "\n".join(
        [
            "부서 | 매출 | 비용 | 인원",
            "영업 | 100 | 40 | 5",
            "개발 | 80 | 30 | 4",
            "기획 | 50 | 20 | 3",
        ]
    )
    assert classify_document_kind(page_count=1, text=text) == DOC_KIND_GENERAL_TEXT


def test_aesop_pdf_is_general_text() -> None:
    matches = sorted(UPLOADS_DIR.glob("06_*.pdf"))
    if not matches:
        pytest.skip("이솝 PDF 없음")
    path = matches[0]
    kind = classify_document_kind(page_count=1, text="x" * 100, pdf_path=path)
    print(f"aesop | {path.name} | kind={kind}")
    assert kind == DOC_KIND_GENERAL_TEXT


def test_arkk_pdf_is_table() -> None:
    matches = sorted(UPLOADS_DIR.glob("ARK_*.pdf"))
    if not matches:
        pytest.skip("ARKK PDF 없음")
    path = matches[0]
    kind = classify_document_kind(page_count=2, text="x" * 200, pdf_path=path)
    print(f"ARKK | {path.name} | kind={kind}")
    assert kind == DOC_KIND_TABLE
