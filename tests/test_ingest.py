"""Phase 0.5 — PDF 로드·청킹·인덱싱·검색 TDD."""

from pathlib import Path

from qdrant_client import QdrantClient

from app.tools.search_documents import search_documents
from ingest.chunk import chunk_pages
from ingest.index_documents import FakeEmbedder, index_chunks
from ingest.load_pdf import load_pdf_pages
from tests.fixtures_helper import SAMPLE_PHRASE, ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_load_pdf_extracts_sample_phrase() -> None:
    """샘플 PDF에서 핵심 문구를 추출한다."""
    pdf_path = ensure_sample_pdf(FIXTURES_DIR)

    pages = load_pdf_pages(pdf_path)

    assert len(pages) >= 1
    combined = " ".join(page.text for page in pages)
    assert SAMPLE_PHRASE in combined
    assert pages[0].source_file == "sample.pdf"
    assert pages[0].page == 1


def test_chunk_pages_attach_metadata() -> None:
    """청크에 source_file, page, chunk_id가 붙는다."""
    pages = load_pdf_pages(ensure_sample_pdf(FIXTURES_DIR))

    chunks = chunk_pages(pages, chunk_size=40, chunk_overlap=10)

    assert len(chunks) >= 1
    first = chunks[0]
    assert first.page_content
    assert first.metadata["source_file"] == "sample.pdf"
    assert first.metadata["page"] == 1
    assert first.metadata["chunk_id"].startswith("sample-")


def test_index_and_search_documents_finds_leave_policy() -> None:
    """샘플 PDF를 인덱싱한 뒤 연차 관련 쿼리로 검색된다."""
    pages = load_pdf_pages(ensure_sample_pdf(FIXTURES_DIR))
    chunks = chunk_pages(pages, chunk_size=80, chunk_overlap=20)
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    collection = "pdf_chunks"

    indexed_count = index_chunks(
        chunks,
        client=client,
        collection_name=collection,
        embedder=embedder,
    )
    assert indexed_count == len(chunks)
    assert indexed_count >= 1

    results = search_documents(
        query="annual leave days",
        client=client,
        collection_name=collection,
        embedder=embedder,
        top_k=3,
    )

    assert len(results) >= 1
    top = results[0]
    assert "page_content" in top
    assert top["metadata"]["source_file"] == "sample.pdf"
    # 검색 결과에 연차 관련 문구가 포함되어야 한다
    all_text = " ".join(item["page_content"] for item in results)
    assert "leave" in all_text.lower() or "fifteen" in all_text.lower()
