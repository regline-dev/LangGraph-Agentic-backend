"""§1 일반 PDF 문서급 메타 — title · created_date."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ingest.chunk import DocumentChunk

# PDF Info CreationDate 예: D:20250715120000Z / D:20250715120000+09'00'
_PDF_DATE_RE = re.compile(
    r"D:(\d{4})(\d{2})(\d{2})",
    re.IGNORECASE,
)


def resolve_title(pdf_path: Path | str, *, fallback_name: str | None = None) -> str:
    """PDF Info Title → 없으면 파일명 stem."""
    path = Path(pdf_path)
    stem_fallback = Path(fallback_name or path.name).stem or "document"
    try:
        reader = PdfReader(str(path))
        meta = reader.metadata
        if meta is not None:
            raw = getattr(meta, "title", None)
            if raw is None and hasattr(meta, "get"):
                raw = meta.get("/Title")
            title = str(raw).strip() if raw else ""
            if title:
                return title
    except Exception:
        # 깨진 Info는 stem으로 폴백
        pass
    return stem_fallback


def resolve_created_date(pdf_path: Path | str) -> str:
    """PDF Creation/ModDate → 없으면 오늘(UTC) YYYY-MM-DD."""
    path = Path(pdf_path)
    try:
        reader = PdfReader(str(path))
        meta = reader.metadata
        if meta is not None:
            for attr, key in (
                ("creation_date", "/CreationDate"),
                ("modification_date", "/ModDate"),
            ):
                value = getattr(meta, attr, None)
                parsed = _coerce_pdf_date(value)
                if parsed:
                    return parsed
                if hasattr(meta, "get"):
                    parsed = _coerce_pdf_date(meta.get(key))
                    if parsed:
                        return parsed
    except Exception:
        pass
    return datetime.now(timezone.utc).date().isoformat()


def build_doc_metadata_fields(
    pdf_path: Path | str,
    *,
    source_file: str | None = None,
) -> dict[str, str]:
    """문서급 title · created_date dict."""
    path = Path(pdf_path)
    return {
        "title": resolve_title(path, fallback_name=source_file or path.name),
        "created_date": resolve_created_date(path),
    }


def stamp_chunks_with_doc_metadata(
    chunks: list[DocumentChunk],
    *,
    title: str,
    created_date: str,
) -> list[DocumentChunk]:
    """청크에 §1 title/created_date 스탬프. 이미 title(우화)이 있으면 유지."""
    stamped: list[DocumentChunk] = []
    for chunk in chunks:
        meta: dict[str, Any] = dict(chunk.metadata)
        if "title" not in meta or meta.get("title") in (None, ""):
            meta["title"] = title
        meta["created_date"] = created_date
        stamped.append(DocumentChunk(page_content=chunk.page_content, metadata=meta))
    return stamped


def _coerce_pdf_date(value: Any) -> str | None:
    """datetime 또는 PDF 날짜 문자열 → YYYY-MM-DD."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    match = _PDF_DATE_RE.search(text)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).date().isoformat()
        except ValueError:
            return None
    # ISO 비슷한 문자열
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None
