"""analyze에 구조 지문 포함 — Phase 3."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.pdf_ingest.analyze import analyze_pdf_bytes


def test_analyze_includes_structure_labels_from_text() -> None:
    """PDF 텍스트 라벨이 structure_labels로 올라온다."""
    fake_pages = [
        SimpleNamespace(
            text="재미도: 4\n원문\n본문입니다.\n키워드\n권력남용\n"
        )
    ]
    with patch("app.pdf_ingest.analyze.load_pdf_pages", return_value=fake_pages), patch(
        "app.pdf_ingest.analyze.classify_document_kind",
        return_value=1,
    ):
        info = analyze_pdf_bytes(
            "sample.pdf",
            b"%PDF-1.4 fake",
            template_labels_by_doc_type={
                "A": {"재미도", "원문", "키워드"},
            },
        )

    assert "structure_labels" in info
    labels = info["structure_labels"]
    assert "재미도" in labels
    assert "원문" in labels
    assert "키워드" in labels
    assert "4" not in labels
    assert "권력남용" not in labels
    assert info["extracted_metadata"]
