"""PDF 상단 헤더 — METADATA_NAME · 타입 수정일/수정자 · 문서생성일."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle


def format_type_updated_stamp(raw: Any) -> str:
    """타입 updated_at → YYYYMMDDHHmm. 파싱 실패 시 빈 문자열."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    # 이미 압축형
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 12:
        return digits[:12]
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text[:26].replace("Z", ""), fmt)
            return dt.strftime("%Y%m%d%H%M")
        except ValueError:
            continue
    return ""


def format_document_created_date(raw: Any | None = None) -> str:
    """문서생성일 YYYY-MM-DD. raw 없으면 오늘."""
    if raw is None or str(raw).strip() == "":
        return datetime.now().strftime("%Y-%m-%d")
    text = str(raw).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return datetime.now().strftime("%Y-%m-%d")


def build_top_header_left(
    *,
    metadata_name: str,
    type_updated_at: Any = None,
    type_updated_by: str | None = None,
) -> str:
    """왼쪽: METADATA_NAME: CODE + 공백4 + PDF 타입 수정일 : stamp / user"""
    name = (metadata_name or "").strip()
    stamp = format_type_updated_stamp(type_updated_at)
    by = (type_updated_by or "").strip()
    parts: list[str] = []
    if name:
        parts.append(f"METADATA_NAME: {name}")
    type_bits: list[str] = []
    if stamp:
        type_bits.append(stamp)
    if by:
        type_bits.append(by)
    if type_bits:
        parts.append(f"PDF 타입 수정일 : {' / '.join(type_bits)}")
    return "    ".join(parts)


def build_top_header_table(
    data: dict,
    *,
    content_width,
    footnote_style,
) -> Table | None:
    """상단 1행 테이블 — 왼쪽 타입 정보 · 오른쪽 문서생성일."""
    from app.fable_pdf.metadata_stamp import normalize_type_code

    meta = normalize_type_code(data.get("type_code") or data.get("metadata_name") or "")
    left = build_top_header_left(
        metadata_name=meta,
        type_updated_at=data.get("type_updated_at"),
        type_updated_by=data.get("type_updated_by"),
    )
    right = f"문서생성일 : {format_document_created_date(data.get('document_created_date'))}"
    if not left and not right:
        return None

    def _esc(t: str) -> str:
        return (
            str(t or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    left_w = content_width * 0.68
    right_w = content_width - left_w
    tbl = Table(
        [
            [
                Paragraph(_esc(left), footnote_style),
                Paragraph(_esc(right), footnote_style),
            ]
        ],
        colWidths=[left_w, right_w],
    )
    tbl.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#6b7280")),
            ]
        )
    )
    return tbl
