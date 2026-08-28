"""영수증 미리보기 PDF — 공급받는자용·공급자용 2페이지, 내용 동일.

웹 미리보기(`frontend_react/src/ocr/OcrTabPanel.jsx`의 `OcrReceiptPreview`)와
같은 표 스타일(테두리·라벨 셀 음영·헤더 음영)로 보이도록 reportlab platypus
Table/TableStyle을 쓴다. 기존(canvas.drawString만 쓰던)방식은 글자만 찍혀
테두리·음영이 전혀 없었다.

공급자 정보 값(등록번호/상호명/대표자/주소/업태/종목)은 웹의
`OCR_SAMPLE_SUPPLIER`(ocrTabConfig.js)와 동일한 샘플 값 — 내용 변경 금지.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from app.fable_pdf.fonts import resolve_korean_font_paths
from app.ocr.kinds import kind_by_id
from app.tools.ocr_receipt import LineItem, totals

# ocrTabConfig.js OCR_SAMPLE_SUPPLIER 와 동일 샘플 값
_SAMPLE_SUPPLIER = {
    "biz_no": "123-45-67890",
    "company": "(주)그린상사",
    "owner": "홍길동",
    "address": "서울특별시 강남구 테헤란로 123",
    "business_type": "도소매",
    "item_category": "사무용품",
}

_BORDER = colors.HexColor("#dfe2e7")
_LABEL_BG = colors.HexColor("#f6f7f9")
_HEAD_BG = colors.HexColor("#eef1f5")
_MUTED = colors.HexColor("#6b7280")
_FOOT = colors.HexColor("#8b91a0")

_CONTENT_WIDTH = A4[0] - 40 * mm


def _ensure_fonts() -> tuple[str, str]:
    if "Noto" not in pdfmetrics.getRegisteredFontNames():
        regular, bold = resolve_korean_font_paths()
        pdfmetrics.registerFont(TTFont("Noto", regular))
        pdfmetrics.registerFont(TTFont("NotoBold", bold))
    return "Noto", "NotoBold"


def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName=bold, fontSize=16, alignment=1, spaceAfter=4
        ),
        "copy": ParagraphStyle(
            "copy",
            fontName=regular,
            fontSize=9,
            textColor=_MUTED,
            alignment=2,
            spaceBefore=16,
            spaceAfter=2,
        ),
        "label": ParagraphStyle("label", fontName=bold, fontSize=8.5, textColor=_MUTED),
        "value": ParagraphStyle("value", fontName=regular, fontSize=8.5),
        "value_right": ParagraphStyle(
            "value_right", fontName=regular, fontSize=8.5, alignment=2
        ),
        "divider": ParagraphStyle(
            "divider",
            fontName=regular,
            fontSize=8,
            alignment=1,
            textColor=_MUTED,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "head": ParagraphStyle("head", fontName=bold, fontSize=8.5, alignment=1),
        # 품목명이 공백 없이 길어도(예: 긴 한글 단어) 셀 너비에서 줄바꿈되도록 CJK 모드 사용.
        "item_name": ParagraphStyle(
            "item_name", fontName=regular, fontSize=8.5, wordWrap="CJK"
        ),
        "item_right": ParagraphStyle(
            "item_right", fontName=regular, fontSize=8.5, alignment=2
        ),
        "total_label": ParagraphStyle("total_label", fontName=bold, fontSize=8.5),
        "total_value": ParagraphStyle(
            "total_value", fontName=bold, fontSize=8.5, alignment=2
        ),
        "footnote": ParagraphStyle(
            "footnote",
            fontName=regular,
            fontSize=7.5,
            alignment=1,
            textColor=_FOOT,
            spaceBefore=8,
        ),
    }


def _fmt_num(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value:,}"


def _supplier_table(styles: dict[str, ParagraphStyle], grand_total: int) -> Table:
    label = styles["label"]
    value = styles["value"]

    def lbl(text: str) -> Paragraph:
        return Paragraph(text, label)

    def val(text: str, style: ParagraphStyle = value) -> Paragraph:
        return Paragraph(str(text), style)

    rows = [
        [lbl("공급자"), lbl("등록번호"), val(_SAMPLE_SUPPLIER["biz_no"]), "", ""],
        ["", lbl("상호명"), val(_SAMPLE_SUPPLIER["company"]), lbl("대표자"), val(_SAMPLE_SUPPLIER["owner"])],
        ["", lbl("사업장주소"), val(_SAMPLE_SUPPLIER["address"]), "", ""],
        ["", lbl("업태"), val(_SAMPLE_SUPPLIER["business_type"]), lbl("종목"), val(_SAMPLE_SUPPLIER["item_category"])],
        ["", lbl("작성일자"), val(date.today().isoformat()), lbl("총공급대가"), val(f"{grand_total:,}원", styles["value_right"])],
        ["", lbl("비고"), val("-"), "", ""],
    ]
    col_w = [
        _CONTENT_WIDTH * 0.14,
        _CONTENT_WIDTH * 0.15,
        _CONTENT_WIDTH * 0.28,
        _CONTENT_WIDTH * 0.15,
        _CONTENT_WIDTH * 0.28,
    ]
    table = Table(rows, colWidths=col_w)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, _BORDER),
                ("SPAN", (0, 0), (0, 5)),  # "공급자" — 전체 행 병합
                ("SPAN", (2, 0), (4, 0)),  # 등록번호 값
                ("SPAN", (2, 2), (4, 2)),  # 사업장주소 값
                ("SPAN", (2, 5), (4, 5)),  # 비고 값
                ("BACKGROUND", (0, 0), (0, -1), _LABEL_BG),
                ("BACKGROUND", (1, 0), (1, -1), _LABEL_BG),
                ("BACKGROUND", (3, 0), (3, -1), _LABEL_BG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _items_table(styles: dict[str, ParagraphStyle], lines: list[LineItem], grand_total: int) -> Table:
    head = styles["head"]
    rows: list[list] = [
        [Paragraph("품명", head), Paragraph("수량", head), Paragraph("단가(원)", head), Paragraph("금액", head)]
    ]
    for item in lines:
        rows.append(
            [
                Paragraph(item.name, styles["item_name"]),
                Paragraph(_fmt_num(item.qty), styles["item_right"]),
                Paragraph(_fmt_num(item.unit_price), styles["item_right"]),
                Paragraph(_fmt_num(item.amount_calc), styles["item_right"]),
            ]
        )
    total_row_idx = len(rows)
    rows.append(
        [
            Paragraph("합계", styles["total_label"]),
            "",
            "",
            Paragraph(_fmt_num(grand_total), styles["total_value"]),
        ]
    )
    col_w = [
        _CONTENT_WIDTH * 0.40,
        _CONTENT_WIDTH * 0.15,
        _CONTENT_WIDTH * 0.20,
        _CONTENT_WIDTH * 0.25,
    ]
    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, _BORDER),
                ("SPAN", (0, total_row_idx), (2, total_row_idx)),
                ("BACKGROUND", (0, 0), (-1, 0), _HEAD_BG),
                ("BACKGROUND", (0, total_row_idx), (-1, total_row_idx), _LABEL_BG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_receipt_pdf_bytes(
    lines: list[LineItem],
    kind_id: str | None,
) -> bytes:
    regular, bold = _ensure_fonts()
    styles = _styles(regular, bold)
    kind = kind_by_id(kind_id)
    title = kind["label"] if kind else "영수증"
    copies = ("공급받는자용", "공급자용")
    grand = totals(lines)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    flow: list = []
    for index, copy_label in enumerate(copies):
        flow.append(Paragraph(title, styles["title"]))
        flow.append(Paragraph(copy_label, styles["copy"]))
        flow.append(_supplier_table(styles, grand))
        flow.append(Paragraph("위 금액을 영수함", styles["divider"]))
        flow.append(_items_table(styles, lines, grand))
        flow.append(
            Paragraph("공급자 정보는 샘플입니다 · 실제 값은 착수 전 확정", styles["footnote"])
        )
        if index < len(copies) - 1:
            flow.append(PageBreak())

    doc.build(flow)
    return buffer.getvalue()
