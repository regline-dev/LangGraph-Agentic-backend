"""Phase 1 — search_documents Tool 단위 테스트."""

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.tools.search_documents import search_documents
from ingest.index_documents import FakeEmbedder, ingest_pdf, store_upload
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_search_documents_rejects_empty_query() -> None:
    """빈 쿼리는 ValueError."""
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)

    with pytest.raises(ValueError, match="query"):
        search_documents(
            "",
            client=client,
            collection_name="pdf_chunks",
            embedder=embedder,
        )


def test_search_documents_returns_hits_after_ingest(tmp_path: Path) -> None:
    """인덱싱 후 관련 쿼리로 결과가 나온다."""
    uploads = tmp_path / "uploads"
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    saved = store_upload(ensure_sample_pdf(FIXTURES_DIR), uploads_dir=uploads)
    ingest_pdf(
        saved,
        client=client,
        collection_name="pdf_chunks",
        embedder=embedder,
        uploads_dir=uploads,
    )

    results = search_documents(
        "annual leave",
        client=client,
        collection_name="pdf_chunks",
        embedder=embedder,
        top_k=2,
    )

    assert len(results) >= 1
    assert "page_content" in results[0]
    assert results[0]["metadata"]["source_file"] == "sample.pdf"
