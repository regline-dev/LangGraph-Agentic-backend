"""PDF 업로드 → data/uploads → Qdrant 적재 (2차-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qdrant_client.http import models as qmodels

from app.config import Settings, get_settings
from app.pdf_ingest.analyze import analyze_pdf_bytes
from app.qdrant_factory import get_shared_qdrant_client
from ingest.embedder_factory import create_embedder
from ingest.index_documents import DEFAULT_UPLOADS_DIR, ingest_pdf


@dataclass(frozen=True)
class PdfIngestResult:
    """HTTP 응답용 적재 결과."""

    source_file: str
    indexed: int
    collection: str
    page_count: int = 0
    metadata: dict[str, Any] | None = None  # 이솝 특화 (없으면 null)
    basic_metadata: dict[str, Any] = field(default_factory=dict)
    is_fable_card: bool = False


@dataclass(frozen=True)
class PdfInspectResult:
    """적재 없이 형식·메타만."""

    is_fable_card: bool
    page_count: int
    basic_metadata: dict[str, Any]
    fable_metadata: dict[str, Any] | None = None


class PdfIngestService:
    """업로드 바이트를 uploads에 저장한 뒤 컬렉션에 적재한다."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        uploads_dir: Path | None = None,
        client=None,
        embedder=None,
        collection_name: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._uploads_dir = (uploads_dir or DEFAULT_UPLOADS_DIR).resolve()
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name or self._settings.qdrant_collection

    def inspect(self, filename: str, content: bytes) -> PdfInspectResult:
        """적재 없이 카드 여부·메타만."""
        if not content:
            raise ValueError("빈 PDF 파일입니다.")
        if not content.lstrip().startswith(b"%PDF"):
            raise ValueError("PDF 형식이 아닙니다.")
        info = analyze_pdf_bytes(filename, content)
        return PdfInspectResult(
            is_fable_card=bool(info["is_fable_card"]),
            page_count=int(info["page_count"]),
            basic_metadata=dict(info["basic_metadata"]),
            fable_metadata=info.get("fable_metadata"),
        )

    def __call__(self, filename: str, content: bytes) -> PdfIngestResult:
        safe_name = _safe_pdf_filename(filename)
        if not content:
            raise ValueError("빈 PDF 파일입니다.")
        if not content.lstrip().startswith(b"%PDF"):
            raise ValueError("PDF 형식이 아닙니다.")

        analyzed = analyze_pdf_bytes(safe_name, content)

        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        destination = self._uploads_dir / safe_name
        destination.write_bytes(content)

        client = self._client or get_shared_qdrant_client(self._settings)
        embedder = self._embedder or create_embedder(self._settings)
        collection = self._collection_name

        _delete_by_source_file(client, collection, safe_name)
        indexed = ingest_pdf(
            destination,
            client=client,
            collection_name=collection,
            embedder=embedder,
            uploads_dir=self._uploads_dir,
        )
        return PdfIngestResult(
            source_file=safe_name,
            indexed=indexed,
            collection=collection,
            page_count=int(analyzed["page_count"]),
            metadata=analyzed.get("fable_metadata"),
            basic_metadata=dict(analyzed["basic_metadata"]),
            is_fable_card=bool(analyzed["is_fable_card"]),
        )


def _safe_pdf_filename(filename: str) -> str:
    """경로 조작 방지 · PDF만 허용."""
    name = Path(filename or "").name.strip()
    if not name:
        raise ValueError("파일명이 비어 있습니다.")
    if Path(name).suffix.lower() != ".pdf":
        raise ValueError("PDF 파일만 업로드할 수 있습니다.")
    return name


def _delete_by_source_file(client, collection: str, source_file: str) -> None:
    """동일 source_file 포인트 삭제 (재업로드 대비)."""
    existing = {item.name for item in client.get_collections().collections}
    if collection not in existing:
        return
    client.delete(
        collection_name=collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="source_file",
                        match=qmodels.MatchValue(value=source_file),
                    )
                ]
            )
        ),
    )


_default_service: PdfIngestService | None = None


def get_pdf_ingest_service() -> PdfIngestService:
    """FastAPI Depends용 싱글톤."""
    global _default_service
    if _default_service is None:
        _default_service = PdfIngestService()
    return _default_service
