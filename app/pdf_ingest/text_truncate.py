"""표(kind=3)용 — find_tables로 표 행을 잘라 LLM에 보낼 원문을 줄인다.

방안 B: 큰 표 **위쪽** 텍스트만 남기고, 표 아래(면책 등)는 보내지 않음.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

DEFAULT_MAX_ROWS_PER_TABLE = 0
MIN_ROWS_TO_TRUNCATE = 10


def _rect_mostly_inside(inner: pymupdf.Rect, outer: pymupdf.Rect, *, min_overlap: float = 0.5) -> bool:
    inter = inner & outer
    if inter.is_empty or inner.get_area() <= 0:
        return False
    return (inter.get_area() / inner.get_area()) >= min_overlap


def _page_text_above_tables(page: pymupdf.Page, table_rects: list[pymupdf.Rect]) -> str:
    """큰 표보다 위에 있는 텍스트 블록만 남김 (표 안·표 아래 제외)."""
    if not table_rects:
        return page.get_text() or ""
    # 페이지에서 가장 위쪽 큰 표의 상단 y
    top_y = min(r.y0 for r in table_rects)
    blocks = page.get_text("blocks") or []
    kept: list[str] = []
    for block in blocks:
        if len(block) < 7 or block[6] != 0:
            continue
        block_rect = pymupdf.Rect(block[:4])
        if any(_rect_mostly_inside(block_rect, tr) for tr in table_rects):
            continue
        # 블록 하단이 표 상단보다 아래면 표 아래/겹침 → 제외
        if block_rect.y1 > top_y + 1:
            continue
        text = (block[4] or "").strip()
        if text:
            kept.append(text)
    return "\n".join(kept)


def _format_table_summary(rows: list, *, omitted: int) -> str:
    lines = ["[표 요약 - 표 전체 대신 일부만 포함]"]
    for row in rows:
        cells = ["" if c is None else str(c).strip() for c in row]
        lines.append(" | ".join(cells))
    if omitted > 0:
        lines.append(f"...(이하 {omitted}행 생략)")
    return "\n".join(lines)


def truncate_repeating_table_rows(
    pdf_path: str | Path,
    *,
    max_rows_per_table: int = DEFAULT_MAX_ROWS_PER_TABLE,
) -> str:
    """큰 표가 있는 페이지: 표 **위** 텍스트 + 표 생략 요약만.

    큰 표가 없는 페이지(보통 뒤쪽 면책)는 보내지 않음 (방안 B).
    """
    path = Path(pdf_path)
    keep = max(0, int(max_rows_per_table))
    doc = pymupdf.open(path)
    try:
        parts: list[str] = []
        saw_large_table = False
        for page in doc:
            tables = list(page.find_tables().tables or [])
            large = [
                t
                for t in tables
                if int(t.row_count or 0) >= MIN_ROWS_TO_TRUNCATE
                and int(t.row_count or 0) > keep
            ]
            if not large:
                # 아직 큰 표를 만나기 전 페이지만 전체 유지, 그 이후는 스킵(면책 등)
                if not saw_large_table:
                    parts.append(page.get_text() or "")
                continue

            saw_large_table = True
            rects = [pymupdf.Rect(t.bbox) for t in large]
            above = _page_text_above_tables(page, rects)
            if above.strip():
                parts.append(above)

            for table in large:
                rows = table.extract() or []
                row_count = int(table.row_count or len(rows) or 0)
                kept_rows = rows[:keep] if keep > 0 else []
                omitted = max(0, row_count - keep)
                parts.append(_format_table_summary(kept_rows, omitted=omitted))

        return "\n".join(parts)
    finally:
        doc.close()


def truncate_repeating_rows(
    text: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS_PER_TABLE,
    min_run: int = 4,
) -> str:
    _ = max_rows
    _ = min_run
    return text if text is not None else ""
