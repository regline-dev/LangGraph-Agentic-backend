"""ARKK holdings 벡터 검색 Tool."""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient

from ingest.index_documents import Embedder

_HOLDINGS_METADATA_KEYS = (
    "fund",
    "as_of_date",
    "as_of_year",
    "doc_type",
    "schema",
)


def search_holdings(
    query: str,
    *,
    client: QdrantClient,
    collection_name: str,
    embedder: Embedder,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """ARKK holdings 컬렉션에서 유사 청크를 검색한다."""
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("query가 비어 있습니다.")
    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")

    query_vector = embedder.embed_texts([cleaned])[0]
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    results: list[dict[str, Any]] = []
    for hit in response.points:
        payload = hit.payload or {}
        metadata: dict[str, Any] = {
            "source_file": payload.get("source_file", ""),
            "page": payload.get("page", 0),
            "chunk_id": payload.get("chunk_id", ""),
        }
        for key in _HOLDINGS_METADATA_KEYS:
            if key in payload:
                metadata[key] = payload[key]

        results.append(
            {
                "page_content": str(payload.get("page_content", "")),
                "metadata": metadata,
                "score": float(hit.score) if hit.score is not None else 0.0,
            }
        )
    return results
