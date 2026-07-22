"""ARKK holdings PDF 전용 ingest — 우화 ingest_pdf와 분리."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest.chunk import chunk_pages
from ingest.holdings_metadata import apply_metadata_to_chunks, load_arkk_manifest
from ingest.index_documents import DEFAULT_UPLOADS_DIR, Embedder, index_chunks
from ingest.load_pdf import load_pdf_pages


def ingest_arkk_pdf(
    pdf_path: Path | str,
    *,
    client,
    collection_name: str,
    embedder: Embedder,
    manifest_entry: dict[str, Any] | None = None,
    uploads_dir: Path | None = None,
) -> int:
    """uploads 아래 holdings PDF를 청킹·메타 스탬프 후 Qdrant에 적재한다."""
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

    entry = manifest_entry or load_arkk_manifest()
    if entry.get("path") and entry["path"] != path.name:
        # manifest path와 실제 파일명이 다르면 manifest 쪽을 실제 파일명으로 맞춤
        entry = {**entry, "path": path.name}

    chunk_size = int(entry.get("chunk_size", 300))
    chunk_overlap = int(entry.get("chunk_overlap", 100))

    pages = load_pdf_pages(path)
    chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    stamped = apply_metadata_to_chunks(
        chunks,
        entry,
        source_file=path.name,
    )
    return index_chunks(
        stamped,
        client=client,
        collection_name=collection_name,
        embedder=embedder,
    )


def ingest_arkk_from_manifest(
    *,
    client,
    collection_name: str,
    embedder: Embedder,
    manifest_path: Path | str | None = None,
    uploads_dir: Path | None = None,
) -> int:
    """manifest 1건 기준으로 uploads 아래 PDF를 ingest한다."""
    entry = load_arkk_manifest(manifest_path)
    root = uploads_dir or DEFAULT_UPLOADS_DIR
    pdf_path = root / entry["path"]
    return ingest_arkk_pdf(
        pdf_path,
        client=client,
        collection_name=collection_name,
        embedder=embedder,
        manifest_entry=entry,
        uploads_dir=root,
    )
