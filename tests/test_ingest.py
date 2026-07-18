"""Phase 0.5+ — PDF 실경로 원칙: 본 코드 진입점을 테스트가 검증만 한다."""

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.tools.search_documents import search_documents
from ingest.chunk import chunk_pages
from ingest.index_documents import (
    DEFAULT_UPLOADS_DIR,
    FakeEmbedder,
    ingest_pdf,
    store_upload,
)
from ingest.load_pdf import load_pdf_pages
from tests.fixtures_helper import SAMPLE_PHRASE, ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_store_upload_copies_into_uploads_dir(tmp_path: Path) -> None:
    """업로드 소스는 data/uploads(또는 주입된 uploads_dir)에 원본으로 저장된다."""
    source = ensure_sample_pdf(FIXTURES_DIR)
    uploads_dir = tmp_path / "uploads"

    saved = store_upload(source, uploads_dir=uploads_dir)

    assert saved == uploads_dir / "sample.pdf"
    assert saved.exists()
    assert saved.read_bytes() == source.read_bytes()


def test_ingest_pdf_rejects_path_outside_uploads(tmp_path: Path) -> None:
    """본 코드는 uploads 밖 경로를 거부한다 (fixture 직접 인제스트 금지)."""
    outside = ensure_sample_pdf(FIXTURES_DIR)
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)

    with pytest.raises(ValueError, match="uploads"):
        ingest_pdf(
            outside,
            client=client,
            collection_name="pdf_chunks",
            embedder=embedder,
            uploads_dir=tmp_path / "uploads",
        )


def test_load_pdf_extracts_sample_phrase() -> None:
    """단위: 로더는 페이지 텍스트를 추출한다 (경로만 넘김)."""
    pdf_path = ensure_sample_pdf(FIXTURES_DIR)

    pages = load_pdf_pages(pdf_path)

    assert len(pages) >= 1
    combined = " ".join(page.text for page in pages)
    assert SAMPLE_PHRASE in combined
    assert pages[0].source_file == "sample.pdf"
    assert pages[0].page == 1


def test_chunk_pages_attach_metadata() -> None:
    """단위: 청크 metadata 계약."""
    pages = load_pdf_pages(ensure_sample_pdf(FIXTURES_DIR))

    chunks = chunk_pages(pages, chunk_size=40, chunk_overlap=10)

    assert len(chunks) >= 1
    first = chunks[0]
    assert first.page_content
    assert first.metadata["source_file"] == "sample.pdf"
    assert first.metadata["page"] == 1
    assert first.metadata["chunk_id"].startswith("sample-")


def test_store_upload_then_ingest_and_search(tmp_path: Path) -> None:
    """E2E: fixture는 업로드 소스일 뿐 → 본 코드 store→ingest→search."""
    source = ensure_sample_pdf(FIXTURES_DIR)
    uploads_dir = tmp_path / "uploads"
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    collection = "pdf_chunks"

    saved = store_upload(source, uploads_dir=uploads_dir)
    indexed_count = ingest_pdf(
        saved,
        client=client,
        collection_name=collection,
        embedder=embedder,
        uploads_dir=uploads_dir,
        chunk_size=80,
        chunk_overlap=20,
    )

    assert indexed_count >= 1
    assert saved.parent == uploads_dir.resolve() or saved.parent == uploads_dir

    results = search_documents(
        query="annual leave days",
        client=client,
        collection_name=collection,
        embedder=embedder,
        top_k=3,
    )

    assert len(results) >= 1
    assert results[0]["metadata"]["source_file"] == "sample.pdf"
    all_text = " ".join(item["page_content"] for item in results)
    assert "leave" in all_text.lower() or "fifteen" in all_text.lower()


def test_default_uploads_dir_points_to_data_uploads() -> None:
    """기본 실경로는 프로젝트 data/uploads 이다."""
    assert DEFAULT_UPLOADS_DIR.name == "uploads"
    assert DEFAULT_UPLOADS_DIR.parent.name == "data"
