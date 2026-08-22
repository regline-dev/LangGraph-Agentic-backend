"""PdfIngestService — uploads 저장·적재 (메모리 Qdrant)."""

from __future__ import annotations

from pathlib import Path
import json

from qdrant_client import QdrantClient

from app.pdf_ingest.document_version import DocumentVersionDecision
from app.pdf_ingest.service import PdfIngestService
from app.pdf_ingest.template_store import PromptTemplate
from ingest.index_documents import FakeEmbedder
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _stub_new_document(**_kwargs) -> DocumentVersionDecision:
    """이 파일의 테스트는 문서 버전 판단 자체(실DB)가 관심사가 아님 — tests/test_document_version.py 참고."""
    return DocumentVersionDecision(action="new_document", document_id=1, version=1, is_current=True)


def test_service_stores_and_indexes_pdf(tmp_path: Path, monkeypatch) -> None:
    """실제 sample.pdf → uploads → FakeEmbed 적재. 템플릿 매칭은 이 테스트 관심사 아님(빈 목록)."""
    monkeypatch.setattr("app.pdf_ingest.service.load_templates", lambda: [])
    monkeypatch.setattr("app.pdf_ingest.service.resolve_document_version", _stub_new_document)
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
    assert payload.get("document_id") == 1
    assert payload.get("version") == 1
    assert payload.get("is_current") is True
    assert result.document_version_action == "new_document"
    assert result.document_id == 1
    assert result.version == 1


def test_service_skip_action_does_not_touch_qdrant(tmp_path: Path, monkeypatch) -> None:
    """스킵 판단이면 임베딩·업서트를 아예 안 한다 — 컬렉션조차 안 생김."""
    monkeypatch.setattr("app.pdf_ingest.service.load_templates", lambda: [])
    monkeypatch.setattr(
        "app.pdf_ingest.service.resolve_document_version",
        lambda **_kwargs: DocumentVersionDecision(
            action="skip", document_id=7, version=2, is_current=True
        ),
    )
    source = ensure_sample_pdf(FIXTURES_DIR)
    client = QdrantClient(":memory:")
    service = PdfIngestService(
        uploads_dir=tmp_path / "uploads",
        client=client,
        embedder=FakeEmbedder(dimension=32),
        collection_name="pdf_chunks_skip_test",
    )

    result = service("sample.pdf", source.read_bytes())

    assert result.indexed == 0
    assert result.document_version_action == "skip"
    assert result.document_id == 7
    assert result.version == 2
    assert "pdf_chunks_skip_test" not in {
        item.name for item in client.get_collections().collections
    }


def test_service_new_version_keeps_old_points_and_flips_is_current(
    tmp_path: Path, monkeypatch
) -> None:
    """새 버전이면 예전 포인트를 지우지 않고 is_current만 false로 내리고, 새 포인트를 추가한다."""
    monkeypatch.setattr("app.pdf_ingest.service.load_templates", lambda: [])
    source = ensure_sample_pdf(FIXTURES_DIR)
    client = QdrantClient(":memory:")
    service = PdfIngestService(
        uploads_dir=tmp_path / "uploads",
        client=client,
        embedder=FakeEmbedder(dimension=32),
        collection_name="pdf_chunks_version_test",
    )

    monkeypatch.setattr("app.pdf_ingest.service.resolve_document_version", _stub_new_document)
    first = service("sample.pdf", source.read_bytes())

    monkeypatch.setattr(
        "app.pdf_ingest.service.resolve_document_version",
        lambda **_kwargs: DocumentVersionDecision(
            action="new_version", document_id=1, version=2, is_current=True
        ),
    )
    second = service("sample.pdf", source.read_bytes())

    assert second.document_version_action == "new_version"
    assert second.version == 2

    points, _ = client.scroll(
        collection_name="pdf_chunks_version_test", limit=50, with_payload=True
    )
    versions_seen = {(p.payload or {}).get("version") for p in points}
    assert versions_seen == {1, 2}
    assert all((p.payload or {}).get("is_current") is False for p in points if (p.payload or {}).get("version") == 1)
    assert all((p.payload or {}).get("is_current") is True for p in points if (p.payload or {}).get("version") == 2)
    assert len(points) == first.indexed + second.indexed


def test_service_stamps_matched_metadata_name_template_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = ensure_sample_pdf(FIXTURES_DIR)
    stub_template = PromptTemplate(
        template_id="A_admin_1",
        name="GUIDE",
        labels=frozenset({"제목", "작성자", "본문"}),
        result_schema={"DOC_TYPE": "A", "METADATA_NAME": "GUIDE"},
        doc_type="A",
    )
    monkeypatch.setattr(
        "app.pdf_ingest.service.load_templates",
        lambda: [stub_template],
    )
    monkeypatch.setattr("app.pdf_ingest.service.resolve_document_version", _stub_new_document)
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


def test_inspect_loads_embedder_before_pdf_analyze(monkeypatch) -> None:
    """Windows: inspect(pymupdf) 후 임베더를 열면 0xC0000005 — 분석 전에 모델을 연다."""
    from app.pdf_ingest.document_version import DocumentVersionPreview

    call_order: list[str] = []

    def fake_create_embedder(settings=None):
        _ = settings
        call_order.append("embedder")
        return FakeEmbedder(dimension=32)

    def fake_analyze(*args, **kwargs):
        _ = args, kwargs
        call_order.append("analyze")
        return {
            "is_fable_card": False,
            "page_count": 1,
            "basic_metadata": {"source_file": "x.pdf", "page_count": 1, "char_count": 10},
            "fable_metadata": None,
            "document_kind": 1,
            "structure_labels": [],
            "extracted_metadata": [],
            "text_excerpt": "",
        }

    monkeypatch.setattr("app.pdf_ingest.service.create_embedder", fake_create_embedder)
    monkeypatch.setattr("app.pdf_ingest.service.analyze_pdf_bytes", fake_analyze)
    monkeypatch.setattr("app.pdf_ingest.service.load_templates", lambda: [])
    monkeypatch.setattr(
        "app.pdf_ingest.service.preview_document_version",
        lambda **_kwargs: DocumentVersionPreview(
            action="new_document", document_id=None, next_version=1
        ),
    )

    service = PdfIngestService()
    service.inspect("x.pdf", b"%PDF-1.4 fake")

    assert call_order[0] == "embedder"
    assert call_order.index("embedder") < call_order.index("analyze")


def test_inspect_keeps_injected_embedder(monkeypatch) -> None:
    """테스트용 주입 임베더는 실모델 로드로 바꾸지 않는다."""
    from app.pdf_ingest.document_version import DocumentVersionPreview

    create_calls: list[str] = []

    def fake_create_embedder(settings=None):
        _ = settings
        create_calls.append("called")
        return FakeEmbedder(dimension=32)

    monkeypatch.setattr("app.pdf_ingest.service.create_embedder", fake_create_embedder)
    monkeypatch.setattr(
        "app.pdf_ingest.service.analyze_pdf_bytes",
        lambda *args, **kwargs: {
            "is_fable_card": False,
            "page_count": 1,
            "basic_metadata": {"source_file": "x.pdf", "page_count": 1, "char_count": 10},
            "fable_metadata": None,
            "document_kind": 1,
            "structure_labels": [],
            "extracted_metadata": [],
            "text_excerpt": "",
        },
    )
    monkeypatch.setattr("app.pdf_ingest.service.load_templates", lambda: [])
    monkeypatch.setattr(
        "app.pdf_ingest.service.preview_document_version",
        lambda **_kwargs: DocumentVersionPreview(
            action="new_document", document_id=None, next_version=1
        ),
    )

    injected = FakeEmbedder(dimension=32)
    service = PdfIngestService(embedder=injected)
    service.inspect("x.pdf", b"%PDF-1.4 fake")
    assert create_calls == []
    assert service._embedder is injected
