"""inspect 템플릿 매칭 연동 — Phase 3."""

from __future__ import annotations

from unittest.mock import patch

from app.pdf_ingest.service import PdfIngestService
from app.pdf_ingest.template_store import PromptTemplate


def test_inspect_match_locks_prompt_when_labels_equal() -> None:
    """지문이 템플릿과 같으면 (레거시 prompt) prompt_locked·template_prompt가 채워진다."""
    labels = frozenset({"재미도", "원문", "키워드", "폭력성"})
    templates = [
        PromptTemplate(
            template_id="fable_v1",
            name="이솝",
            labels=labels,
            prompt="잠긴 프롬프트",
            doc_type="A",
        )
    ]
    service = PdfIngestService()
    with patch(
        "app.pdf_ingest.service.analyze_pdf_bytes",
        return_value={
            "is_fable_card": False,
            "page_count": 1,
            "basic_metadata": {"source_file": "x.pdf", "page_count": 1, "char_count": 10},
            "fable_metadata": None,
            "document_kind": 1,
            "structure_labels": sorted(labels),
            "extracted_metadata": [
                {"label": "재미도", "value": "4", "source": "colon"},
            ],
            "text_excerpt": "본문",
        },
    ):
        with patch(
            "app.pdf_ingest.service.load_templates",
            return_value=templates,
        ):
            result = service.inspect("x.pdf", b"%PDF-1.4 fake")

    assert result.template_match_status == "match"
    assert result.prompt_locked is True
    assert result.template_prompt == "잠긴 프롬프트"
    assert result.template_id == "fable_v1"
    assert result.extracted_metadata == [
        {"label": "재미도", "value": "4", "source": "colon"},
    ]


def test_inspect_match_uses_result_schema_fill_prompt() -> None:
    labels = frozenset({"재미도", "원문", "키워드", "폭력성"})
    schema = {"재미도": 2, "원문": "예시"}
    templates = [
        PromptTemplate(
            template_id="fable_v1",
            name="이솝",
            labels=labels,
            prompt="무시될 옛 지시문",
            result_schema=schema,
            doc_type="A",
        )
    ]
    service = PdfIngestService()
    with patch(
        "app.pdf_ingest.service.analyze_pdf_bytes",
        return_value={
            "is_fable_card": False,
            "page_count": 1,
            "basic_metadata": {"source_file": "x.pdf", "page_count": 1, "char_count": 10},
            "fable_metadata": None,
            "document_kind": 1,
            "structure_labels": sorted(labels),
            "extracted_metadata": [
                {"label": "재미도", "value": "4", "source": "colon"},
            ],
            "text_excerpt": "본문",
        },
    ):
        with patch(
            "app.pdf_ingest.service.load_templates",
            return_value=templates,
        ):
            result = service.inspect("x.pdf", b"%PDF-1.4 fake")

    assert result.prompt_locked is True
    assert result.result_schema == schema
    assert result.filled_result is not None
    assert result.filled_result["source_file"] == "x.pdf"
    assert result.filled_result["재미도"] == "4"
    assert result.template_prompt is not None
    assert "결과 양식" in result.template_prompt
    assert "재미도" in result.template_prompt
