"""§1 일반 메타 — title · created_date 해석 (TDD)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from app.pdf_ingest.doc_metadata import (
    resolve_created_date,
    resolve_title,
    stamp_chunks_with_doc_metadata,
)
from ingest.chunk import DocumentChunk


def _write_pdf_with_info(path: Path, *, title: str | None = None, creation: str | None = None) -> None:
    """최소 PDF + Info 딕셔너리."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # 텍스트가 있어야 load_pdf_pages가 통과 — 빈 페이지는 실패하므로 나중에 analyze는 별도
    if title is not None or creation is not None:
        info = DictionaryObject()
        if title is not None:
            info[NameObject("/Title")] = TextStringObject(title)
        if creation is not None:
            info[NameObject("/CreationDate")] = TextStringObject(creation)
        writer._info = info  # noqa: SLF001 — 테스트용 Info 주입
    writer.write(path)


def test_resolve_title_uses_pdf_info_then_stem(tmp_path: Path) -> None:
    path = tmp_path / "holdings_report.pdf"
    _write_pdf_with_info(path, title="ARK Innovation ETF")
    assert resolve_title(path) == "ARK Innovation ETF"

    bare = tmp_path / "no_title.pdf"
    _write_pdf_with_info(bare)
    assert resolve_title(bare) == "no_title"


def test_resolve_created_date_from_pdf_or_utc_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "dated.pdf"
    # PDF 날짜 형식 D:YYYYMMDDHHmmSS
    _write_pdf_with_info(path, creation="D:20250715120000Z")
    assert resolve_created_date(path) == "2025-07-15"

    bare = tmp_path / "undated.pdf"
    _write_pdf_with_info(bare)
    fixed = datetime(2026, 7, 23, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return fixed if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr("app.pdf_ingest.doc_metadata.datetime", _FixedDateTime)
    assert resolve_created_date(bare) == "2026-07-23"


def test_stamp_chunks_adds_title_and_created_date_keeps_fable_title() -> None:
    plain = DocumentChunk(
        page_content="hello",
        metadata={"source_file": "a.pdf", "page": 1, "chunk_id": "a-001"},
    )
    fable = DocumentChunk(
        page_content="story",
        metadata={
            "source_file": "f.pdf",
            "page": 1,
            "chunk_id": "f-001",
            "title": "늑대와 어린양",
            "fable_id": 1,
        },
    )
    stamped = stamp_chunks_with_doc_metadata(
        [plain, fable],
        title="파일제목",
        created_date="2026-07-23",
    )
    assert stamped[0].metadata["title"] == "파일제목"
    assert stamped[0].metadata["created_date"] == "2026-07-23"
    assert stamped[1].metadata["title"] == "늑대와 어린양"  # 우화 title 유지
    assert stamped[1].metadata["created_date"] == "2026-07-23"
