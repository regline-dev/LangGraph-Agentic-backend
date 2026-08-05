"""관리자 메타 JSON — search_labels 스탬프·고정사전∪가변 한글→영문 키 해석."""

from __future__ import annotations

import json
from typing import Any

from ingest.chunk import DocumentChunk

from app.pdf_ingest.global_labels import SEARCH_LABELS_KEY, load_global_labels

# 고정 메타 전역 사전 = data/GLOBAL_LABELS.json (문서 search_labels에 반복 저장하지 않음)
FIXED_FIELD_LABELS: dict[str, str] = load_global_labels()


def parse_admin_meta_json(text: str | None) -> dict[str, Any] | None:
    """벡터화 prompt가 결과 JSON이면 dict, 아니면 None."""
    raw = (text or "").strip()
    if not raw or raw[0] not in "{[":
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def merge_label_map(search_labels: dict[str, Any] | None) -> dict[str, str]:
    """고정 사전 ∪ 문서 search_labels(가변). 고정 키는 사전 우선."""
    merged: dict[str, str] = dict(FIXED_FIELD_LABELS)
    if isinstance(search_labels, dict):
        for en_key, korean in search_labels.items():
            key = str(en_key).strip()
            if not key or key in FIXED_FIELD_LABELS:
                continue
            merged[key] = "" if korean is None else str(korean)
    return merged


def resolve_search_key(query: str, search_labels: dict[str, Any] | None) -> str | None:
    """한글 검색명 또는 영문 키 → 정본 영문 키 (고정사전∪가변)."""
    q = (query or "").strip()
    if not q:
        return None
    labels = merge_label_map(search_labels)
    if q in labels:
        return q
    lower = q.lower()
    for en_key, korean in labels.items():
        en = str(en_key).strip()
        if en.lower() == lower:
            return en_key if isinstance(en_key, str) else str(en_key)
        ko = str(korean).strip() if korean is not None else ""
        if ko == q or ko.lower() == lower:
            return en_key if isinstance(en_key, str) else str(en_key)
    return None


def stamp_chunks_with_admin_meta(
    chunks: list[DocumentChunk],
    admin_meta: dict[str, Any] | None,
) -> list[DocumentChunk]:
    """결과 JSON 스칼라·search_labels(가변)를 청크 메타에 심는다."""
    if not admin_meta or not isinstance(admin_meta, dict):
        return chunks
    search_labels = admin_meta.get(SEARCH_LABELS_KEY)
    labels: dict[str, Any] = (
        dict(search_labels) if isinstance(search_labels, dict) else {}
    )
    stamped: list[DocumentChunk] = []
    for chunk in chunks:
        meta: dict[str, Any] = dict(chunk.metadata)
        if labels:
            meta[SEARCH_LABELS_KEY] = labels
        for key, value in admin_meta.items():
            if key == SEARCH_LABELS_KEY:
                continue
            if isinstance(value, (dict, list)):
                continue
            meta[str(key)] = value
        stamped.append(DocumentChunk(page_content=chunk.page_content, metadata=meta))
    return stamped
