"""admin_meta — search_labels 스탬프·해석."""

from ingest.chunk import DocumentChunk

from app.pdf_ingest.admin_meta import (
    parse_admin_meta_json,
    resolve_search_key,
    stamp_chunks_with_admin_meta,
)


def test_parse_admin_meta_json_accepts_kind3_result() -> None:
    text = """{
  "As of": "11/26/2025",
  "SCHEMA": "ARKK",
  "search_labels": {"As of": "데이터기준일"}
}"""
    meta = parse_admin_meta_json(text)
    assert meta is not None
    assert meta["As of"] == "11/26/2025"
    assert meta["search_labels"]["As of"] == "데이터기준일"


def test_parse_admin_meta_json_rejects_instruction_text() -> None:
    assert parse_admin_meta_json("당신은 문서에서...") is None


def test_resolve_search_key_korean_and_english() -> None:
    labels = {"As of": "데이터기준일", "Note": "메모"}
    assert resolve_search_key("데이터기준일", labels) == "As of"
    assert resolve_search_key("As of", labels) == "As of"
    assert resolve_search_key("제목", labels) == "title"
    assert resolve_search_key("title", None) == "title"
    assert resolve_search_key("메모", labels) == "Note"
    assert resolve_search_key("없음", labels) is None


def test_stamp_chunks_with_admin_meta_sets_as_of_and_labels() -> None:
    chunks = [
        DocumentChunk(
            page_content="holdings",
            metadata={"source_file": "a.pdf", "page": 1, "chunk_id": "a_1_0"},
        )
    ]
    admin = {
        "As of": "11/26/2025",
        "SCHEMA": "ARKK",
        "search_labels": {"As of": "데이터기준일"},
    }
    out = stamp_chunks_with_admin_meta(chunks, admin)
    assert out[0].metadata["As of"] == "11/26/2025"
    assert out[0].metadata["SCHEMA"] == "ARKK"
    assert out[0].metadata["search_labels"]["As of"] == "데이터기준일"
