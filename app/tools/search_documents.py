"""PDF 문서 검색 Tool — Phase 0.5에서는 인덱스 검증용, Phase 1에서 LangGraph Tool로 연결."""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingest.index_documents import Embedder

# is_current=False로 명시된 포인트(예전 버전)만 제외 — 필드 자체가 없는 레거시 포인트는
# 그대로 검색된다(문서 버전 관리 적용 전 데이터 회귀 방지). 계획: Docs/20260814_벡터화_문서버전관리_계획.md
_EXCLUDE_STALE_VERSION_FILTER = qmodels.Filter(
    must_not=[
        qmodels.FieldCondition(key="is_current", match=qmodels.MatchValue(value=False))
    ]
)


def search_documents(
    query: str,
    *,
    client: QdrantClient,
    collection_name: str,
    embedder: Embedder,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """쿼리와 유사한 PDF 청크를 반환한다.

    Returns:
        [{ "page_content": str, "metadata": {source_file, page, chunk_id}, "score": float }, ...]
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("query가 비어 있습니다.")
    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")

    query_vector = embedder.embed_texts([cleaned])[0]
    # qdrant-client 1.12+ 는 search 대신 query_points 사용
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=_EXCLUDE_STALE_VERSION_FILTER,
        limit=top_k,
        with_payload=True,
    )

    results: list[dict[str, Any]] = []
    for hit in response.points:
        payload = hit.payload or {}
        results.append(
            {
                "page_content": str(payload.get("page_content", "")),
                "metadata": {
                    "source_file": payload.get("source_file", ""),
                    "page": payload.get("page", 0),
                    "chunk_id": payload.get("chunk_id", ""),
                },
                "score": float(hit.score) if hit.score is not None else 0.0,
            }
        )
    return results
