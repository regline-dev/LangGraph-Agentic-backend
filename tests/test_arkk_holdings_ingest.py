"""ARKK holdings ingest — 메타·manifest·Qdrant payload 계약 (TDD)."""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from ingest.chunk import chunk_pages
from ingest.holdings_metadata import (
    MetadataRuleError,
    apply_metadata_to_chunks,
    build_chunk_metadata,
    load_arkk_manifest,
    validate_manifest_entry,
)
from ingest.index_documents import FakeEmbedder, store_upload
from ingest.ingest_arkk import ingest_arkk_pdf
from ingest.load_pdf import PdfPage
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MANIFEST = FIXTURES_DIR / "arkk_manifest_sample.yaml"


def test_validate_manifest_entry_holdings_normalizes_fields() -> None:
    """holdings manifest 1행 — 필수 필드·chunk 크기 정규화."""
    entry = validate_manifest_entry(
        {
            "schema": "holdings",
            "path": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
            "as_of_date": "2025-11-26",
            "fund": "ARKK",
            "doc_type": "holdings",
            "loader": "pdfplumber",
            "chunk_size": 300,
            "chunk_overlap": 100,
        }
    )

    assert entry["schema"] == "holdings"
    assert entry["fund"] == "ARKK"
    assert entry["as_of_date"] == "2025-11-26"
    assert entry["chunk_size"] == 300
    assert entry["chunk_overlap"] == 100


def test_validate_manifest_entry_rejects_bad_date() -> None:
    """as_of_date 형식이 틀리면 MetadataRuleError."""
    with pytest.raises(MetadataRuleError, match="as_of_date"):
        validate_manifest_entry(
            {
                "path": "x.pdf",
                "as_of_date": "2025/11/26",
            }
        )


def test_build_chunk_metadata_required_keys() -> None:
    """청크 metadata — source_file·as_of_date·as_of_year·fund."""
    meta = build_chunk_metadata(
        source_file="ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
        as_of_date="2025-11-26",
        fund="ARKK",
    )

    assert meta["source_file"] == "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf"
    assert meta["as_of_date"] == "2025-11-26"
    assert meta["as_of_year"] == 2025
    assert meta["fund"] == "ARKK"
    assert meta["doc_type"] == "holdings"
    assert meta["schema"] == "holdings"


def test_load_arkk_manifest_reads_documents_entry() -> None:
    """fixture manifest에서 holdings 문서 1건을 읽는다."""
    entry = load_arkk_manifest(SAMPLE_MANIFEST)

    assert entry["path"] == "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf"
    assert entry["fund"] == "ARKK"
    assert entry["as_of_date"] == "2025-11-26"


def test_apply_metadata_stamps_chunk_pages() -> None:
    """청크 리스트에 holdings metadata가 page 번호와 함께 붙는다."""
    pages = [
        PdfPage(
            text="Tesla Inc 12.5% As of 11/26/2025",
            source_file="ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
            page=1,
        ),
    ]
    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=100)
    manifest_entry = validate_manifest_entry(
        {
            "path": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
            "as_of_date": "2025-11-26",
            "fund": "ARKK",
        }
    )

    stamped = apply_metadata_to_chunks(
        chunks,
        manifest_entry,
        source_file="ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
    )

    assert len(stamped) >= 1
    first = stamped[0]
    assert first.metadata["fund"] == "ARKK"
    assert first.metadata["as_of_year"] == 2025
    assert first.metadata["page"] == 1


def test_ingest_arkk_pdf_indexes_holdings_payload(tmp_path: Path) -> None:
    """uploads 경로 PDF → arkk 컬렉션 payload에 holdings 필드."""
    source = ensure_sample_pdf(FIXTURES_DIR)
    uploads_dir = tmp_path / "uploads"
    saved = store_upload(source, uploads_dir=uploads_dir)

    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    manifest_entry = validate_manifest_entry(
        {
            "path": saved.name,
            "as_of_date": "2025-11-26",
            "fund": "ARKK",
            "chunk_size": 40,
            "chunk_overlap": 10,
        }
    )

    indexed = ingest_arkk_pdf(
        saved,
        client=client,
        collection_name="arkk_holdings_test",
        embedder=embedder,
        manifest_entry=manifest_entry,
        uploads_dir=uploads_dir,
    )

    assert indexed >= 1
    points, _ = client.scroll(
        collection_name="arkk_holdings_test",
        limit=1,
        with_payload=True,
    )
    assert points
    payload = points[0].payload or {}
    assert payload.get("fund") == "ARKK"
    assert payload.get("as_of_date") == "2025-11-26"
    assert payload.get("as_of_year") == 2025
    assert payload.get("doc_type") == "holdings"
    assert payload.get("page_content")


def test_ingest_arkk_pdf_rejects_path_outside_uploads(tmp_path: Path) -> None:
    """uploads 밖 경로는 ingest_arkk_pdf가 거부한다."""
    outside = ensure_sample_pdf(FIXTURES_DIR)
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)

    with pytest.raises(ValueError, match="uploads"):
        ingest_arkk_pdf(
            outside,
            client=client,
            collection_name="arkk_holdings_test",
            embedder=embedder,
            manifest_entry={"path": outside.name, "as_of_date": "2025-11-26"},
            uploads_dir=tmp_path / "uploads",
        )
