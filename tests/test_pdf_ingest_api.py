"""2차 순번 4 — POST /pdf/inspect · /pdf/ingest HTTP 계약."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.pdf_ingest.service import (
    PdfIngestResult,
    PdfInspectResult,
    get_pdf_ingest_service,
)

client = TestClient(app)

_FAKE_PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@dataclass
class _OkService:
    def inspect(self, filename: str, content: bytes) -> PdfInspectResult:
        _ = content
        return PdfInspectResult(
            is_fable_card=True,
            page_count=1,
            basic_metadata={"source_file": filename, "page_count": 1, "char_count": 10},
            fable_metadata={"fable_id": 1, "title": "테스트"},
        )

    def __call__(self, filename: str, content: bytes) -> PdfIngestResult:
        _ = content
        return PdfIngestResult(
            source_file=filename,
            indexed=5,
            collection="pdf_chunks_bge",
            page_count=1,
            metadata={
                "fable_id": 1,
                "title": "늑대와 어린양",
                "ending_tone": "비관",
                "final_grade": "A",
                "keywords": ["늑대", "양"],
            },
            basic_metadata={"source_file": filename, "page_count": 1, "char_count": 100},
            is_fable_card=True,
        )


@dataclass
class _FailService:
    def inspect(self, filename: str, content: bytes) -> PdfInspectResult:
        _ = filename, content
        raise RuntimeError("boom")

    def __call__(self, filename: str, content: bytes) -> PdfIngestResult:
        _ = filename, content
        raise RuntimeError("Qdrant unavailable")


def test_ingest_rejects_non_pdf_filename() -> None:
    app.dependency_overrides[get_pdf_ingest_service] = lambda: _OkService()
    try:
        response = client.post(
            "/pdf/ingest",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_ingest_returns_enriched_fields() -> None:
    app.dependency_overrides[get_pdf_ingest_service] = lambda: _OkService()
    try:
        response = client.post(
            "/pdf/ingest",
            files={"file": ("01_늑대.pdf", _FAKE_PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["source_file"] == "01_늑대.pdf"
        assert body["indexed"] == 5
        assert body["page_count"] == 1
        assert body["is_fable_card"] is True
        assert body["metadata"]["title"] == "늑대와 어린양"
        assert body["basic_metadata"]["page_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_inspect_returns_fable_flag() -> None:
    app.dependency_overrides[get_pdf_ingest_service] = lambda: _OkService()
    try:
        response = client.post(
            "/pdf/inspect",
            files={"file": ("card.pdf", _FAKE_PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_fable_card"] is True
        assert body["page_count"] == 1
        assert body["fable_metadata"]["title"] == "테스트"
    finally:
        app.dependency_overrides.clear()


def test_ingest_pipeline_failure_returns_502() -> None:
    app.dependency_overrides[get_pdf_ingest_service] = lambda: _FailService()
    try:
        response = client.post(
            "/pdf/ingest",
            files={"file": ("sample.pdf", _FAKE_PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 502
    finally:
        app.dependency_overrides.clear()
