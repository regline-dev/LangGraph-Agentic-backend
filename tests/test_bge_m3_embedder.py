"""bge-m3 Embedder — 모델은 mock, 계약·차원만 검증."""

from __future__ import annotations

from typing import Any

import pytest

from ingest.bge_m3 import BGE_M3_DIMENSION, BgeM3Embedder
from ingest.index_documents import _ensure_collection
from qdrant_client import QdrantClient


class _FakeSTModel:
    """SentenceTransformer 자리 대체."""

    def __init__(self, dim: int = BGE_M3_DIMENSION) -> None:
        self._dim = dim

    def get_sentence_embedding_dimension(self) -> int:
        return self._dim

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
        rows: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self._dim
            vec[0] = float(len(text) % 97) / 97.0
            vec[1] = 1.0
            if normalize_embeddings:
                norm = sum(v * v for v in vec) ** 0.5 or 1.0
                vec = [v / norm for v in vec]
            rows.append(vec)
        return rows


def test_bge_m3_embedder_returns_fixed_dimension() -> None:
    embedder = BgeM3Embedder(model_name="BAAI/bge-m3", model=_FakeSTModel())
    assert embedder.dimension == BGE_M3_DIMENSION
    vectors = embedder.embed_texts(["박쥐", "늑대와 어린양 이야기"])
    assert len(vectors) == 2
    assert len(vectors[0]) == BGE_M3_DIMENSION
    assert vectors[0] != vectors[1]


def test_ensure_collection_recreates_when_dimension_mismatches(tmp_path) -> None:
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    name = "pdf_chunks_test"
    _ensure_collection(client, name, dimension=32)
    _ensure_collection(client, name, dimension=BGE_M3_DIMENSION)
    info = client.get_collection(name)
    size = info.config.params.vectors.size
    assert size == BGE_M3_DIMENSION
