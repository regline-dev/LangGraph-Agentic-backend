"""Qdrant payload에서 우화 title로 metadata 조회."""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


def list_fable_titles(
    *,
    client: QdrantClient,
    collection_name: str,
    limit: int = 2000,
) -> list[str]:
    """컬렉션에 있는 우화 title 목록(중복 제거)."""
    titles: set[str] = set()
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=min(256, limit),
            offset=next_offset,
            with_payload=["title"],
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            title = str(payload.get("title") or "").strip()
            if title:
                titles.add(title)
            if len(titles) >= limit:
                return sorted(titles, key=len, reverse=True)
        if next_offset is None:
            break
    return sorted(titles, key=len, reverse=True)


def list_fable_metas(
    *,
    client: QdrantClient,
    collection_name: str,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """우화별 metadata 요약(title, fun 등) — 제목당 첫 payload."""
    by_title: dict[str, dict[str, Any]] = {}
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=min(256, limit),
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = dict(point.payload or {})
            title = str(payload.get("title") or "").strip()
            if not title or title in by_title:
                continue
            keywords = payload.get("keywords")
            if isinstance(keywords, str):
                payload["keywords"] = [part for part in keywords.split("|") if part.strip()]
            by_title[title] = payload
            if len(by_title) >= limit:
                return list(by_title.values())
        if next_offset is None:
            break
    return list(by_title.values())


def lookup_fable_metadata_by_title(
    title: str,
    *,
    client: QdrantClient,
    collection_name: str,
) -> dict[str, Any] | None:
    """title이 일치하는 포인트 하나의 payload를 metadata dict로 반환."""
    cleaned = (title or "").strip()
    if not cleaned:
        return None

    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="title",
                    match=qmodels.MatchValue(value=cleaned),
                )
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        return None

    payload = dict(points[0].payload or {})
    keywords = payload.get("keywords")
    if isinstance(keywords, str):
        payload["keywords"] = [part for part in keywords.split("|") if part.strip()]
    return payload


def fetch_fable_body_by_title(
    title: str,
    content_type: str,
    *,
    client: QdrantClient,
    collection_name: str,
) -> dict[str, Any] | None:
    """title + content_type(origin|modern) 청크를 모아 본문 그대로 반환.

    Returns:
        { "text": str, "citations": [{source_file, page, snippet}, ...] } 또는 None
    """
    cleaned_title = (title or "").strip()
    cleaned_type = (content_type or "").strip()
    if not cleaned_title or cleaned_type not in {"origin", "modern"}:
        return None

    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="title",
                    match=qmodels.MatchValue(value=cleaned_title),
                ),
                qmodels.FieldCondition(
                    key="content_type",
                    match=qmodels.MatchValue(value=cleaned_type),
                ),
            ]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        return None

    # chunk_id 순으로 본문 이어 붙이기 (교훈이 뒤 청크에 있어도 누락 방지)
    ordered = sorted(
        points,
        key=lambda point: str((point.payload or {}).get("chunk_id") or ""),
    )
    parts: list[str] = []
    citations: list[dict[str, Any]] = []
    seen_pages: set[tuple[str, int]] = set()
    for point in ordered:
        payload = point.payload or {}
        text = str(payload.get("page_content") or "").strip()
        if text:
            parts.append(text)
        source_file = str(payload.get("source_file") or "")
        page = int(payload.get("page") or 0)
        key = (source_file, page)
        if key not in seen_pages and (source_file or page):
            seen_pages.add(key)
            citations.append(
                {
                    "source_file": source_file,
                    "page": page,
                    "snippet": text[:200],
                }
            )

    if not parts:
        return None
    return {"text": _join_chunk_texts(parts), "citations": citations}


def _join_chunk_texts(parts: list[str]) -> str:
    """청크 overlap이 있으면 겹친 접두를 건너뛰고 이어 붙인다."""
    if not parts:
        return ""
    merged = parts[0]
    for next_part in parts[1:]:
        overlap_size = 0
        max_check = min(len(merged), len(next_part), 120)
        for size in range(max_check, 19, -1):
            if merged.endswith(next_part[:size]):
                overlap_size = size
                break
        if overlap_size:
            merged = merged + next_part[overlap_size:]
        else:
            merged = merged + "\n" + next_part
    return merged
