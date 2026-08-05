"""A/C 공통 규칙형 메타데이터 추출기 TDD."""

from __future__ import annotations

from pathlib import Path

from app.pdf_ingest.doc_kind import DOC_KIND_GENERAL_TEXT, classify_document_kind
from app.pdf_ingest.metadata_extract import extract_metadata_candidates


def test_extracts_colon_fullwidth_colon_and_pipe_rows() -> None:
    text = (
        "담당부서: 고객지원\n"
        "발행일：2026-08-02\n"
        "부서 | 매출 | 비용\n"
        "영업 | 100 | 40\n"
    )

    extracted = extract_metadata_candidates(text)

    assert {"label": "담당부서", "value": "고객지원", "source": "colon"} in extracted
    assert {"label": "발행일", "value": "2026-08-02", "source": "colon"} in extracted
    assert {"label": "부서", "value": "영업", "source": "pipe"} in extracted
    assert {"label": "매출", "value": "100", "source": "pipe"} in extracted
    assert {"label": "비용", "value": "40", "source": "pipe"} in extracted


def test_extracts_configured_label_from_next_line_or_inline_value() -> None:
    text = "작성자\n홍길동\nAs of 11/26/2025\n"

    extracted = extract_metadata_candidates(
        text,
        known_labels={"작성자", "As of"},
    )

    assert {"label": "작성자", "value": "홍길동", "source": "known_next_line"} in extracted
    assert {"label": "As of", "value": "11/26/2025", "source": "known_inline"} in extracted


def test_plain_prose_without_structure_returns_no_candidates() -> None:
    text = "춘향은 이몽룡과 백년가약을 맺었다. 두 사람은 다시 만나기를 약속했다."

    assert extract_metadata_candidates(text) == []


def test_fable_fixture_uses_configured_labels_without_document_name_branch() -> None:
    text = (
        Path(__file__).parent / "fixtures" / "fable_pdf_06_extract.txt"
    ).read_text(encoding="utf-8")
    configured_labels = {
        "결말톤",
        "재미도",
        "폭력성",
        "교훈 명확도",
        "키워드",
        "예상 낭독시간",
        "등장인물",
        "대사비중",
        "분량",
        "최종평가",
        "원문",
        "한마디 결론",
    }

    extracted = extract_metadata_candidates(text, known_labels=configured_labels)

    assert {"label": "결말톤", "value": "해피", "source": "colon"} in extracted
    assert {"label": "재미도", "value": "2 / 5", "source": "known_next_line"} in extracted
    assert {"label": "키워드", "value": "단결", "source": "known_next_line"} in extracted
    assert not any(item["label"] == "이솝우화 #6" for item in extracted)
    assert (
        classify_document_kind(page_count=2, text=text)
        == DOC_KIND_GENERAL_TEXT
    )
