"""find_tables 표 행 전처리 — 참조 truncate_repeating_table_rows.py."""

from pathlib import Path

import pytest

from app.pdf_ingest.text_truncate import truncate_repeating_table_rows

UPLOADS = Path(__file__).resolve().parents[1] / "data" / "uploads"


def test_arkk_pdf_table_rows_stripped() -> None:
    path = next(iter(sorted(UPLOADS.glob("ARK_*.pdf"))), None)
    if path is None:
        pytest.skip("ARKK PDF 없음")
    out = truncate_repeating_table_rows(path, max_rows_per_table=0)
    assert "생략" in out
    assert "TSLA" not in out
    assert "As of" in out or "ARK" in out
    # 방안 B: 표 아래 면책 문구는 없어야 함
    assert "Investors should carefully" not in out
    assert "FDIC" not in out


def test_aesop_pdf_unchanged_enough() -> None:
    """표가 작거나 없으면 본문이 유지된다 (kind=1 경로에서는 호출 안 하지만 안전 확인)."""
    path = next(iter(sorted(UPLOADS.glob("06_*.pdf"))), None)
    if path is None:
        pytest.skip("이솝 PDF 없음")
    out = truncate_repeating_table_rows(path, max_rows_per_table=0)
    # 우화 본문 키워드가 남아야 함
    assert "아버지" in out or "아들" in out
