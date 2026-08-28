"""타입 구성 기반 PDF 레이아웃 (비이솝). 이솝 도감·내용 평가 하드코딩 없음."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.fable_pdf.pdf_generator import _styles

# A4 좌우 여백 22mm 기준 본문 폭 — 가로 카드가 이 폭을 꽉 채움
TYPED_CONTENT_WIDTH = 166 * mm
TYPED_SECTION_FONT_SIZE = 7.5
# 카드형 값 — 리스트형(9.5pt)과 맞춤. statvalue(13pt)는 이솝 stat 카드 전용이라 재사용 안 함
TYPED_CARD_VALUE_FONT_SIZE = 9.5


def typed_section_style() -> ParagraphStyle:
    """그룹 제목(이용 안내 등) — 기본 section보다 작게."""
    _styles()  # 폰트 등록
    return ParagraphStyle(
        "typed_section",
        fontName="Noto",
        fontSize=TYPED_SECTION_FONT_SIZE,
        leading=TYPED_SECTION_FONT_SIZE + 2,
        textColor=colors.HexColor("#898781"),
        spaceBefore=8,
        spaceAfter=4,
    )


def typed_card_value_style(accent: bool = False) -> ParagraphStyle:
    """카드형(가로) 값 — 리스트형 행과 같은 크기로 맞춘 굵은 글씨."""
    _styles()  # 폰트 등록
    return ParagraphStyle(
        "typed_card_value_accent" if accent else "typed_card_value",
        fontName="NotoBold",
        fontSize=TYPED_CARD_VALUE_FONT_SIZE,
        leading=TYPED_CARD_VALUE_FONT_SIZE + 3,
        textColor=colors.HexColor("#0b0b0b"),
    )


def _escape(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_group_table(
    fields: dict,
    *,
    layout: str,
    styles: dict,
    content_width: float = TYPED_CONTENT_WIDTH,
) -> Table:
    """
    layout=horizontal → 카드형(가로) 한 행 (개수와 무관하게 content_width 꽉 채움).
    그 외 → 리스트형(세로) 라벨|값 표.
    """
    items = [(str(k), str(v or "-")) for k, v in fields.items()]
    if not items:
        return Table([[Paragraph("-", styles["body"])]], colWidths=[content_width])

    layout_key = (layout or "vertical").strip().lower()
    if layout_key == "horizontal":
        n = len(items)
        # 3개든 4개든 본문 폭을 N등분 — max 캡으로 오른쪽 여백이 생기지 않게
        cell_w = content_width / n
        inner_w = max(cell_w - 4 * mm, 12 * mm)

        def card_cell(label: str, value: str, accent: bool) -> Table:
            value_style = typed_card_value_style(accent)
            return Table(
                [
                    [Paragraph(_escape(label), styles["statlabel"])],
                    [Paragraph(_escape(value), value_style)],
                ],
                colWidths=[inner_w],
            )

        cells = [
            card_cell(label, value, index == n - 1)
            for index, (label, value) in enumerate(items)
        ]
        tbl = Table([cells], colWidths=[cell_w] * n)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1EFE8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        if n >= 1:
            style_cmds.append(
                ("BACKGROUND", (n - 1, 0), (n - 1, 0), colors.HexColor("#EAF3DE"))
            )
        tbl.setStyle(TableStyle(style_cmds))
        tbl.hAlign = "LEFT"
        return tbl

    # 리스트형(세로) — 라벨 열 + 값 열 = content_width
    label_w = 40 * mm
    value_w = content_width - label_w
    rows = [[_escape(label), _escape(value)] for label, value in items]
    tbl = Table(rows, colWidths=[label_w, value_w])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Noto"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#52514e")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e1e0d9")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return tbl


def generate_typed_pdf(data: dict, output_path: str) -> str:
    """
    data 키: id, title, body_text, source_note, type_name,
             groups{그룹:{라벨:값}}, group_layouts{그룹:vertical|horizontal},
             subtitles{제목:내용}, tags[]
    """
    s = _styles()
    section_style = typed_section_style()
    side_margin = 22 * mm
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=side_margin,
        rightMargin=side_margin,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    flow = []

    # 상단: METADATA_NAME · 타입 수정일/수정자 | 문서생성일
    from app.fable_pdf.pdf_header import build_top_header_table

    header_tbl = build_top_header_table(
        data, content_width=TYPED_CONTENT_WIDTH, footnote_style=s["footnote"]
    )
    if header_tbl is not None:
        flow.append(header_tbl)
        flow.append(Spacer(1, 6))

    type_name = str(data.get("type_name") or "PDF").strip() or "PDF"
    flow.append(Paragraph(_escape(f"{type_name} · 안내 카드"), s["eyebrow"]))

    badge_tbl = Table(
        [[Paragraph(_escape(f"{type_name} #{data.get('id', '')}"), s["badge_blue"])]],
        colWidths=[50 * mm],
    )
    badge_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#E6F1FB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    badge_tbl.hAlign = "LEFT"
    flow.append(badge_tbl)
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(_escape(data.get("title") or "(제목 없음)"), s["title"]))

    groups = data.get("groups") if isinstance(data.get("groups"), dict) else {}
    layouts = (
        data.get("group_layouts") if isinstance(data.get("group_layouts"), dict) else {}
    )
    for group_name, fields in groups.items():
        if not isinstance(fields, dict) or not fields:
            continue
        flow.append(Paragraph(_escape(str(group_name)), section_style))
        layout = str((layouts or {}).get(group_name) or "vertical")
        flow.append(
            build_group_table(
                fields,
                layout=layout,
                styles=s,
                content_width=TYPED_CONTENT_WIDTH,
            )
        )
        flow.append(Spacer(1, 4))

    tags = list(data.get("tags") or [])
    if tags:
        flow.append(Paragraph("키워드", section_style))
        tag_cells = [Paragraph(_escape(str(t)), s["tag"]) for t in tags]
        tags_tbl = Table([tag_cells], colWidths=[30 * mm] * max(1, len(tag_cells)))
        tags_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1EFE8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        tags_tbl.hAlign = "LEFT"
        flow.append(tags_tbl)
        flow.append(Spacer(1, 8))

    flow.append(Paragraph("원문", section_style))
    origin_lines = [
        ln.strip() for ln in str(data.get("body_text") or "").split("\n") if ln.strip()
    ]
    origin_html = "<br/>".join(_escape(ln) for ln in origin_lines)
    flow.append(Paragraph(origin_html or "-", s["body_indent"]))
    flow.append(Spacer(1, 8))

    subtitles = data.get("subtitles") if isinstance(data.get("subtitles"), dict) else {}
    for sub_title, sub_body in (subtitles or {}).items():
        flow.append(Paragraph(_escape(str(sub_title)), section_style))
        modern = _escape(sub_body)
        modern_box = Table(
            [[Paragraph(modern or "-", s["body"])]],
            colWidths=[TYPED_CONTENT_WIDTH],
        )
        modern_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1EFE8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        flow.append(modern_box)
        flow.append(Spacer(1, 8))

    flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e1e0d9")))
    flow.append(Spacer(1, 4))
    source_note = str(data.get("source_note") or "")
    flow.append(Paragraph(_escape(f"※ 원문 출처: {source_note}"), s["footnote"]))

    doc.build(flow)
    return output_path
