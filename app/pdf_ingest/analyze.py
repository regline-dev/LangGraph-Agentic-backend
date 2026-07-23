"""PDF 바이트 검사·메타 추출 (적재 전 inspect / ingest 공통)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ingest.fable_parse import parse_fable_card
from ingest.load_pdf import load_pdf_pages

try:
    from app.fable_pdf.keyword_normalize import normalize_keyword_tags
except ImportError:  # pragma: no cover
    def normalize_keyword_tags(tags):  # type: ignore[misc]
        return list(tags or []) or ["우화"]

try:
    from app.pdf_ingest.doc_metadata import build_doc_metadata_fields
except ImportError:  # pragma: no cover
    def build_doc_metadata_fields(pdf_path, *, source_file=None):  # type: ignore[misc]
        from pathlib import Path as _P

        stem = _P(source_file or _P(pdf_path).name).stem
        from datetime import datetime, timezone

        return {
            "title": stem or "document",
            "created_date": datetime.now(timezone.utc).date().isoformat(),
        }


def analyze_pdf_bytes(filename: str, content: bytes) -> dict[str, Any]:
    """임시 파일로 로드 후 페이지·기본/특화 메타를 반환.

    Returns:
        is_fable_card, page_count, basic_metadata, fable_metadata(nullable)
    """
    safe_name = Path(filename or "upload.pdf").name
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    with tempfile.TemporaryDirectory(prefix="pdf_inspect_") as tmp:
        path = Path(tmp) / safe_name
        path.write_bytes(content)
        pages = load_pdf_pages(path)
        joined = "\n".join(p.text for p in pages if p.text and p.text.strip())
        fable = parse_fable_card(joined)
        doc_fields = build_doc_metadata_fields(path, source_file=safe_name)

        basic = {
            "source_file": safe_name,
            "page_count": len(pages),
            "char_count": len(joined),
            "title": doc_fields["title"],
            "created_date": doc_fields["created_date"],
        }
        fable_meta = None
        if fable is not None:
            fable_meta = {
                "fable_id": fable["fable_id"],
                "title": fable["title"],
                "ending_tone": fable["ending_tone"],
                "fun": fable["fun"],
                "violence": fable["violence"],
                "moral_clarity": fable["moral_clarity"],
                "reading_seconds": fable["reading_seconds"],
                "characters_count": fable["characters_count"],
                "dialogue_ratio": fable["dialogue_ratio"],
                "char_count": fable["char_count"],
                "final_grade": fable["final_grade"],
                "keywords": normalize_keyword_tags(fable["keywords"]),
            }

        return {
            "is_fable_card": fable is not None,
            "page_count": len(pages),
            "basic_metadata": basic,
            "fable_metadata": fable_meta,
        }
