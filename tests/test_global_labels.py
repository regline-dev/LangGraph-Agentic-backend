"""GLOBAL_LABELS · template_id · result_schema 정규화."""

from app.pdf_ingest.global_labels import (
    build_template_id,
    doc_kind_to_letter,
    load_global_labels,
    normalize_result_schema,
    sanitize_login_id,
)


def test_load_global_labels_has_agreed_keys_in_order() -> None:
    labels = load_global_labels()
    keys = list(labels.keys())
    assert keys[0] == "DOC_TYPE"
    assert keys[1] == "METADATA_NAME"
    assert keys[2] == "DESCRIPTION"
    assert labels["DESCRIPTION"] == "설명"
    assert "pdf_created_at" in keys
    assert "vector_updated_at" == keys[-1]
    assert labels["DOC_TYPE"] == "문서타입명"
    assert labels["METADATA_NAME"] == "메타데이터 템플릿명"
    assert labels["template_created_by"] == "템플릿 등록자"
    assert "created_date" not in labels
    assert "modify_date" not in labels


def test_doc_kind_to_letter_and_template_id() -> None:
    assert doc_kind_to_letter(1) == "A"
    assert doc_kind_to_letter(2) == "B"
    assert doc_kind_to_letter(3) == "C"
    assert doc_kind_to_letter(4) == "D"
    assert doc_kind_to_letter(99) == "X"
    assert sanitize_login_id("counsel1") == "counsel1"
    assert sanitize_login_id("a/b c") == "a_b_c"
    assert sanitize_login_id("") == "guest"
    assert (
        build_template_id(document_kind=3, login_id="counsel1", timestamp_ms=1785541236324)
        == "C_counsel1_1785541236324"
    )


def test_normalize_result_schema_fills_all_global_keys_in_order() -> None:
    out = normalize_result_schema(
        {
            "METADATA_NAME": "ARKK",
            "As of": "11/26/2025",
            "created_date": "2025-11-26",
            "search_labels": {"As of": "데이터기준일"},
            "title": "holdings",
        }
    )
    keys = list(out.keys())
    assert keys[0] == "DOC_TYPE"
    assert keys[1] == "METADATA_NAME"
    assert keys[2] == "DESCRIPTION"
    assert keys[-1] == "search_labels"
    assert "As of" in keys
    assert keys.index("As of") > keys.index("vector_updated_at")
    assert out["DOC_TYPE"] == ""
    assert out["METADATA_NAME"] == "ARKK"
    assert out["title"] == "holdings"
    assert out["source_file"] == ""
    assert out["pdf_created_at"] == "2025-11-26"
    assert out["As of"] == "11/26/2025"
    assert out["search_labels"] == {"As of": "데이터기준일"}
    assert "created_date" not in out
