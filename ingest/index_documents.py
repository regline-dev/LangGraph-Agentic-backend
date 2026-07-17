"""인덱싱 — 임베딩 후 Qdrant(pdf_chunks) 적재. FAQ qa_*와 분리."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingest.chunk import DocumentChunk


class Embedder(Protocol):
    """임베딩 인터페이스 — 실 API/학습용 Fake 모두 동일 계약."""

    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class FakeEmbedder:
    """학습·테스트용 결정적 임베딩 (API 키 불필요).

    단어 토큰 해시를 고정 차원에 누적해, 같은 문구는 비슷한 벡터가 된다.
    실서비스에서는 OpenAI/Google 등으로 교체한다.
    """

    def __init__(self, dimension: int = 32) -> None:
        if dimension <= 0:
            raise ValueError("dimension은 1 이상이어야 합니다.")
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            tokens = ["empty"]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def index_chunks(
    chunks: list[DocumentChunk],
    *,
    client: QdrantClient,
    collection_name: str,
    embedder: Embedder,
) -> int:
    """청크를 임베딩해 Qdrant 컬렉션에 upsert한다. 적재 개수를 반환."""
    if not chunks:
        raise ValueError("인덱싱할 청크가 없습니다.")
    if not collection_name:
        raise ValueError("collection_name이 비어 있습니다.")

    _ensure_collection(client, collection_name, embedder.dimension)
    vectors = embedder.embed_texts([chunk.page_content for chunk in chunks])

    points = [
        qmodels.PointStruct(
            id=_stable_point_id(chunk.metadata["chunk_id"]),
            vector=vector,
            payload={
                "page_content": chunk.page_content,
                "source_file": chunk.metadata["source_file"],
                "page": chunk.metadata["page"],
                "chunk_id": chunk.metadata["chunk_id"],
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


def _ensure_collection(client: QdrantClient, collection_name: str, dimension: int) -> None:
    """컬렉션이 없으면 cosine 벡터 컬렉션을 생성한다."""
    existing = {item.name for item in client.get_collections().collections}
    if collection_name in existing:
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=dimension, distance=qmodels.Distance.COSINE),
    )


def _stable_point_id(chunk_id: str) -> int:
    """chunk_id → Qdrant unsigned int id (결정적)."""
    digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**63)
