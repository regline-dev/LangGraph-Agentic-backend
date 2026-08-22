"""template_id payload 저장과 A/C 템플릿 벡터 삭제 TDD."""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.pdf_ingest.service import PdfIngestService
from ingest.chunk import DocumentChunk
from ingest.index_documents import _chunk_payload


def test_chunk_payload_keeps_template_id() -> None:
    chunk = DocumentChunk(
        page_content="본문",
        metadata={
            "source_file": "guide.pdf",
            "page": 1,
            "chunk_id": "guide_1_0",
            "template_id": "A_admin_1",
        },
    )

    assert _chunk_payload(chunk)["template_id"] == "A_admin_1"


@pytest.mark.parametrize("template_id", ["A_admin_1", "C_admin_2"])
def test_delete_prompt_template_removes_same_template_vectors(
    monkeypatch,
    template_id: str,
) -> None:
    deleted_ids: list[str] = []
    monkeypatch.setattr(
        "app.pdf_ingest.service.soft_delete_template",
        lambda tid: deleted_ids.append(tid),
    )

    client = QdrantClient(":memory:")
    collection = "template_delete_test"
    client.create_collection(
        collection_name=collection,
        vectors_config=qmodels.VectorParams(
            size=2,
            distance=qmodels.Distance.COSINE,
        ),
    )
    client.upsert(
        collection_name=collection,
        points=[
            qmodels.PointStruct(
                id=1,
                vector=[1.0, 0.0],
                payload={"template_id": template_id},
            ),
            qmodels.PointStruct(
                id=2,
                vector=[0.0, 1.0],
                payload={"template_id": "other"},
            ),
        ],
    )
    service = PdfIngestService(
        client=client,
        collection_name=collection,
    )

    result = service.delete_prompt_template(
        template_id=template_id,
        delete_vectors=True,
    )

    assert result["soft_deleted"] is True
    assert deleted_ids == [template_id]
    points, _ = client.scroll(
        collection_name=collection,
        limit=10,
        with_payload=True,
    )
    remaining_template_ids = {
        (point.payload or {}).get("template_id")
        for point in points
    }
    assert template_id not in remaining_template_ids
    assert "other" in remaining_template_ids
