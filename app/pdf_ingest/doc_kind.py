"""표 행 감지 상수·판별 — find_tables 행 수."""

from __future__ import annotations

from pathlib import Path

import pymupdf

# 합의·테스트와 동일 — 작은 부가 표 vs 표 중심
MIN_TABLE_ROWS_FOR_KIND = 10

DOC_KIND_GENERAL_TEXT = 1
DOC_KIND_SCAN_IMAGE = 2
DOC_KIND_TABLE = 3
DOC_KIND_COMPLEX_LAYOUT = 4

DOC_KIND_UNDEVELOPED_MESSAGES = {
    DOC_KIND_SCAN_IMAGE: "스캔본/이미지이며 아직 미개발입니다.",
    # 3(표)은 본줄 개발 — 미개발 목록에서 제외
    DOC_KIND_COMPLEX_LAYOUT: "복합 레이아웃이며 아직 미개발입니다.",
}


def _pdf_has_large_table(pdf_path: Path, *, min_rows: int = MIN_TABLE_ROWS_FOR_KIND) -> bool:
    """find_tables — row_count >= min_rows 인 표가 있으면 True."""
    doc = pymupdf.open(pdf_path)
    try:
        for page in doc:
            for table in page.find_tables().tables:
                if int(table.row_count or 0) >= min_rows:
                    return True
        return False
    finally:
        doc.close()


def classify_document_kind(
    *,
    page_count: int,
    text: str,
    pdf_path: str | Path | None = None,
    min_table_rows: int = MIN_TABLE_ROWS_FOR_KIND,
) -> int:
    """문서 특성 코드. 표는 PDF 경로의 find_tables·행 수로만 판별 (1번에 표 로직 없음)."""
    pages = max(1, int(page_count or 1))
    joined = (text or "").strip()
    char_count = len(joined)

    # 글자가 너무 적으면 스캔/이미지(2)
    if char_count < 40 * pages:
        return DOC_KIND_SCAN_IMAGE

    # 표 중심(3) — 경로 있을 때만 구조 신호
    if pdf_path is not None:
        path = Path(pdf_path)
        if path.is_file() and _pdf_has_large_table(path, min_rows=min_table_rows):
            return DOC_KIND_TABLE

    # 나머지 일반 텍스트(1). 복합(4)은 아직 미사용
    return DOC_KIND_GENERAL_TEXT


def undeveloped_message(kind: int) -> str | None:
    """미개발 종류면 안내 문구. 1·3은 None."""
    return DOC_KIND_UNDEVELOPED_MESSAGES.get(int(kind))
