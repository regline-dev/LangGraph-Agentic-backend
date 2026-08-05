"""결과 양식 템플릿 + 이번 PDF 값 → filled_result (inspect 자동 채움)."""

from __future__ import annotations

from typing import Any

from app.pdf_ingest.global_labels import (
    DOC_KIND_LETTER,
    global_label_keys,
    normalize_result_schema,
)

# DOC_TYPE 저장값 = A|B|C|D (합의)
_DOC_TYPE_BY_KIND: dict[int, str] = dict(DOC_KIND_LETTER)

# basic_metadata → result 키
_BASIC_OVERLAY = (
    ("source_file", "source_file"),
    ("page_count", "page_count"),
    ("char_count", "char_count"),
    ("title", "title"),
    ("created_date", "pdf_created_at"),
)

def fill_result_schema_from_document(
    result_schema: dict[str, Any] | None,
    *,
    basic_metadata: dict[str, Any] | None = None,
    text_excerpt: str = "",
    document_kind: int | None = None,
    extracted_metadata: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """템플릿 양식에 이번 문서 값을 덮어쓴 dict. 양식 없으면 None."""
    if not isinstance(result_schema, dict) or not result_schema:
        return None

    filled = normalize_result_schema(result_schema)
    basic = basic_metadata if isinstance(basic_metadata, dict) else {}
    candidates = [
        item
        for item in (extracted_metadata or [])
        if isinstance(item, dict)
        and str(item.get("label") or "").strip()
        and str(item.get("value") or "").strip()
    ]

    try:
        kind = int(document_kind) if document_kind is not None else 0
    except (TypeError, ValueError):
        kind = 0

    # DOC_TYPE — 비어 있거나 구 "3 (표중심)" 형이면 문자 코드로
    current_doc = str(filled.get("DOC_TYPE") or "").strip()
    if kind in _DOC_TYPE_BY_KIND:
        letter = _DOC_TYPE_BY_KIND[kind]
        if not current_doc or current_doc[0].isdigit() or "표중심" in current_doc:
            filled["DOC_TYPE"] = letter

    for src_key, dest_key in _BASIC_OVERLAY:
        if dest_key not in filled:
            continue
        raw = basic.get(src_key)
        if raw is None or raw == "":
            continue
        # 문서 고유값은 이번 PDF 것으로 교체
        filled[dest_key] = raw

    search_labels = filled.get("search_labels")
    label_by_key = search_labels if isinstance(search_labels, dict) else {}
    global_keys = set(global_label_keys())

    # 템플릿의 가변 값은 이전 PDF 값을 재사용하지 않는다.
    for key in tuple(filled):
        if key not in global_keys and key != "search_labels":
            filled[key] = ""
    for key in label_by_key:
        if key in filled:
            filled[key] = ""

    candidate_lookup = {
        str(item["label"]).strip().casefold(): str(item["value"]).strip()
        for item in candidates
    }
    for destination_key in tuple(filled):
        configured_label = label_by_key.get(destination_key, destination_key)
        value = candidate_lookup.get(str(configured_label).strip().casefold())
        if value is None:
            value = candidate_lookup.get(str(destination_key).strip().casefold())
        if value is not None:
            filled[destination_key] = value

    return normalize_result_schema(filled)
