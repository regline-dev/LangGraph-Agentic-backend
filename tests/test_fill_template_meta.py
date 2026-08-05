"""템플릿 양식 + 문서값 → filled_result."""

from app.pdf_ingest.fill_template_meta import fill_result_schema_from_document


def test_fill_overlays_basic_and_as_of() -> None:
    schema = {
        "DOC_TYPE": "",
        "SCHEMA": "ARKK",
        "source_file": "old.pdf",
        "page_count": 1,
        "As of": "",
        "search_labels": {"As of": "데이터기준일"},
    }
    filled = fill_result_schema_from_document(
        schema,
        basic_metadata={
            "source_file": "ARKK.pdf",
            "page_count": 3,
            "char_count": 100,
            "title": "holdings",
            "created_date": "2025-11-26",
        },
        text_excerpt="As of 11/26/2025\nTicker...",
        document_kind=3,
        extracted_metadata=[
            {"label": "데이터기준일", "value": "11/26/2025", "source": "known_inline"},
        ],
    )
    assert filled is not None
    assert filled["DOC_TYPE"] == "C"
    assert filled["METADATA_NAME"] == "ARKK"
    assert filled["source_file"] == "ARKK.pdf"
    assert filled["page_count"] == 3
    assert filled["pdf_created_at"] == "2025-11-26"
    assert filled["As of"] == "11/26/2025"
    assert filled["search_labels"]["As of"] == "데이터기준일"
    assert list(filled.keys())[0] == "DOC_TYPE"
    assert list(filled.keys())[-1] == "search_labels"


def test_fill_returns_none_without_schema() -> None:
    assert fill_result_schema_from_document(None) is None
    assert fill_result_schema_from_document({}) is None


def test_fill_maps_extracted_values_and_blanks_missing_template_values() -> None:
    schema = {
        "DOC_TYPE": "A",
        "author": "이전 문서 작성자",
        "published_date": "2025-01-01",
        "search_labels": {
            "author": "작성자",
            "published_date": "발행일",
        },
    }

    filled = fill_result_schema_from_document(
        schema,
        document_kind=1,
        extracted_metadata=[
            {"label": "작성자", "value": "홍길동", "source": "colon"},
        ],
    )

    assert filled is not None
    assert filled["author"] == "홍길동"
    assert filled["published_date"] == ""
