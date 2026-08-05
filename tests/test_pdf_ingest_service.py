"""PdfIngestService — uploads 저장·적재 (메모리 Qdrant)."""

from __future__ import annotations

from pathlib import Path
import json

from qdrant_client import QdrantClient

from app.pdf_ingest.service import PdfIngestService
from app.pdf_ingest.template_store import PromptTemplate, save_template
from ingest.index_documents import FakeEmbedder
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_service_stores_and_indexes_pdf(tmp_path: Path) -> None:
    """실제 sample.pdf → uploads → FakeEmbed 적재."""
    source = ensure_sample_pdf(FIXTURES_DIR)
    content = source.read_bytes()
    uploads = tmp_path / "uploads"
    client = QdrantClient(":memory:")
    service = PdfIngestService(
        uploads_dir=uploads,
        client=client,
        embedder=FakeEmbedder(dimension=32),
        collection_name="pdf_chunks_test",
    )

    result = service("sample.pdf", content)

    assert result.source_file == "sample.pdf"
    assert result.indexed >= 1
    assert result.collection == "pdf_chunks_test"
    assert (uploads / "sample.pdf").exists()
    assert "title" in result.basic_metadata
    assert result.basic_metadata["title"]
    assert "created_date" in result.basic_metadata
    assert len(result.basic_metadata["created_date"]) == 10  # YYYY-MM-DD

    points, _ = client.scroll(collection_name="pdf_chunks_test", limit=5, with_payload=True)
    assert points
    payload = points[0].payload or {}
    assert payload.get("title")
    assert payload.get("created_date") == result.basic_metadata["created_date"]


def test_service_stamps_matched_metadata_name_template_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = ensure_sample_pdf(FIXTURES_DIR)
    template_dir = tmp_path / "templates"
    monkeypatch.setattr(
        "app.pdf_ingest.template_store.DEFAULT_TEMPLATE_STORE_DIR",
        template_dir,
    )
    save_template(
        PromptTemplate(
            template_id="A_admin_1",
            name="GUIDE",
            labels=frozenset({"제목", "작성자", "본문"}),
            result_schema={"DOC_TYPE": "A", "METADATA_NAME": "GUIDE"},
            doc_type="A",
        ),
        store_dir=template_dir,
    )
    client = QdrantClient(":memory:")
    service = PdfIngestService(
        uploads_dir=tmp_path / "uploads",
        client=client,
        embedder=FakeEmbedder(dimension=32),
        collection_name="template_payload_test",
    )

    service(
        "guide.pdf",
        source.read_bytes(),
        prompt=json.dumps(
            {"DOC_TYPE": "A", "METADATA_NAME": "GUIDE"},
            ensure_ascii=False,
        ),
    )

    points, _ = client.scroll(
        collection_name="template_payload_test",
        limit=5,
        with_payload=True,
    )
    assert points
    assert (points[0].payload or {}).get("template_id") == "A_admin_1"
