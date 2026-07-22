"""인덱싱 — 임베딩 후 Qdrant(pdf_chunks) 적재. FAQ qa_*와 분리.

PDF 실경로 원칙:
  업로드 → data/uploads/원본.pdf 저장 → load_pdf_pages → 청킹 → Qdrant
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
from pathlib import Path
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingest.chunk import DocumentChunk, chunk_pages
from ingest.load_pdf import load_pdf_pages

# 프로젝트 루트/data/uploads — README Locked 실경로
DEFAULT_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"


def store_upload(source_path: Path | str, *, uploads_dir: Path | None = None) -> Path:
    """업로드 소스를 uploads 디렉터리에 원본 파일명으로 저장하고 경로를 반환한다.

    Args:
        source_path: 사용자가 올린(또는 지정한) PDF 경로
        uploads_dir: 저장 디렉터리 (기본: data/uploads)

    Raises:
        FileNotFoundError: 소스가 없을 때
        ValueError: PDF가 아닐 때
    """
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"업로드 소스가 없습니다: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"PDF만 저장할 수 있습니다: {source}")

    target_dir = (uploads_dir or DEFAULT_UPLOADS_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / source.name
    shutil.copy2(source, destination)
    return destination


def ingest_pdf(
    pdf_path: Path | str,
    *,
    client: QdrantClient,
    collection_name: str,
    embedder: Embedder,
    uploads_dir: Path | None = None,
    chunk_size: int = 300,
    chunk_overlap: int = 60,
) -> int:
    """uploads 아래 PDF만 로드→청킹→Qdrant 적재한다. 적재 개수를 반환.

    tests/fixtures 등 uploads 밖 경로로 직접 호출하면 ValueError.
    """
    path = Path(pdf_path).resolve()
    allowed_root = (uploads_dir or DEFAULT_UPLOADS_DIR).resolve()

    if not path.exists():
        raise FileNotFoundError(f"PDF가 없습니다: {path}")
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"PDF는 uploads 디렉터리 아래여야 합니다: {allowed_root} (받은 경로: {path})"
        ) from exc

    pages = load_pdf_pages(path)
    chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return index_chunks(
        chunks,
        client=client,
        collection_name=collection_name,
        embedder=embedder,
    )


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
            payload=_chunk_payload(chunk),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


def _chunk_payload(chunk: DocumentChunk) -> dict:
    """청크 payload — 기본 필드 + 우화 metadata(있으면)."""
    payload: dict = {
        "page_content": chunk.page_content,
        "source_file": chunk.metadata["source_file"],
        "page": chunk.metadata["page"],
        "chunk_id": chunk.metadata["chunk_id"],
    }
    # 필터 검색용 우화 필드 (없으면 생략 — 일반 PDF 회귀)
    for key in (
        "content_type",
        "fable_id",
        "title",
        "ending_tone",
        "fun",
        "violence",
        "moral_clarity",
        "reading_seconds",
        "characters_count",
        "dialogue_ratio",
        "char_count",
        "final_grade",
        "keywords",
        # ARKK holdings
        "fund",
        "as_of_date",
        "as_of_year",
        "doc_type",
        "schema",
    ):
        if key in chunk.metadata:
            payload[key] = chunk.metadata[key]
    return payload


def _vector_size_from_collection(client: QdrantClient, collection_name: str) -> int | None:
    """컬렉션 벡터 차원. 알 수 없으면 None."""
    info = client.get_collection(collection_name)
    vectors = info.config.params.vectors
    if vectors is None:
        return None
    size = getattr(vectors, "size", None)
    if size is not None:
        return int(size)
    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        nested = getattr(first, "size", None)
        if nested is not None:
            return int(nested)
    return None


def _ensure_collection(client: QdrantClient, collection_name: str, dimension: int) -> None:
    """컬렉션이 없거나 벡터 차원이 다르면 cosine 컬렉션을 (재)생성한다."""
    existing = {item.name for item in client.get_collections().collections}
    if collection_name in existing:
        current_size = _vector_size_from_collection(client, collection_name)
        # 차원을 못 읽으면 안전하게 재생성
        if current_size is not None and current_size == dimension:
            return
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=dimension, distance=qmodels.Distance.COSINE),
    )


def _stable_point_id(chunk_id: str) -> int:
    """chunk_id → Qdrant unsigned int id (결정적)."""
    digest = hashlib.sha256(chunk_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**63)
