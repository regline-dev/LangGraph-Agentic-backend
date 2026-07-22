"""우화 분석 카드 PDF 생성 (reportlab + matplotlib 레이더)."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.fable_pdf.fonts import resolve_korean_font_paths

ENDING_TONE_SCORE = {"해피": 5, "중립": 3, "새드": 1}
READING_CHARS_PER_SEC = 5.3

_fonts_ready = False
_font_prop: fm.FontProperties | None = None


def _ensure_fonts() -> fm.FontProperties:
    """나눔/맑은고딕을 reportlab·matplotlib에 한 번만 등록한다."""
    global _fonts_ready, _font_prop
    if _fonts_ready and _font_prop is not None:
        return _font_prop

    regular, bold = resolve_korean_font_paths()
    if "Noto" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Noto", regular))
    if "NotoBold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("NotoBold", bold))

    _font_prop = fm.FontProperties(fname=regular)
    try:
        fm.fontManager.addfont(regular)
    except (ValueError, RuntimeError):
        pass
    plt.rcParams["font.family"] = _font_prop.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    _fonts_ready = True
    return _font_prop


def compute_structure_stats(body_text: str, characters: list[str]) -> dict:
    """글자수 기반 구조 통계 (LLM 불필요)."""
    char_count = len(body_text)
    dialogue = re.findall(r"[\"\u201c\u201d][^\"\u201c\u201d]*[\"\u201c\u201d]", body_text)
    dialogue_chars = sum(len(d) for d in dialogue)
    dialogue_ratio = round(dialogue_chars / char_count * 100, 0) if char_count else 0

    reading_seconds = round(char_count / READING_CHARS_PER_SEC)
    shorts_ok = reading_seconds <= 60
    difficulty_low = len(characters) <= 2
    dialogue_high = dialogue_ratio >= 50

    positives = sum([shorts_ok, difficulty_low, dialogue_high])
    grade_map = {0: "아쉬움", 1: "보통", 2: "좋음", 3: "아주좋음"}
    if positives == 3 and reading_seconds <= 30:
        final_grade = "최고"
    else:
        final_grade = grade_map[positives]

    return {
        "char_count": char_count,
        "reading_seconds": reading_seconds,
        "shorts_label": "쇼츠 적합" if shorts_ok else "일반 영상",
        "difficulty_label": "난이도 낮음" if difficulty_low else "난이도 보통",
        "dialogue_ratio": int(dialogue_ratio),
        "dialogue_label": "몰입도 높음" if dialogue_high else "몰입도 보통",
        "expected_pages": max(1, round(char_count / 250)),
        "final_grade": final_grade,
    }


def make_radar_chart(
    fun: int,
    violence: int,
    moral_clarity: int,
    ending_tone: str,
    out_path: str,
) -> None:
    """재미/폭력/교훈/결말톤 레이더 차트 PNG."""
    font_prop = _ensure_fonts()
    labels = ["재미도", "폭력성", "교훈", "결말톤"]
    values = [fun, violence, moral_clarity, ENDING_TONE_SCORE.get(ending_tone, 3)]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values_c = values + values[:1]
    angles_c = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(3.6, 3.2), subplot_kw=dict(polar=True))
    ax.plot(angles_c, values_c, color="#2a78d6", linewidth=2)
    ax.fill(angles_c, values_c, color="#2a78d6", alpha=0.12)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontproperties=font_prop, fontsize=11, color="#52514e")
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels([])
    ax.spines["polar"].set_color("#e1e0d9")
    ax.grid(color="#e1e0d9")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, transparent=True)
    plt.close(fig)


def _styles() -> dict[str, ParagraphStyle]:
    _ensure_fonts()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            fontName="Noto",
            fontSize=8.5,
            textColor=colors.HexColor("#898781"),
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "title",
            fontName="NotoBold",
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#0b0b0b"),
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Noto",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#52514e"),
            spaceAfter=10,
            firstLineIndent=10,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Noto",
            fontSize=9.5,
            textColor=colors.HexColor("#898781"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Noto",
            fontSize=10,
            textColor=colors.HexColor("#0b0b0b"),
            leading=16,
        ),
        "body_indent": ParagraphStyle(
            "body_indent",
            fontName="Noto",
            fontSize=10,
            textColor=colors.HexColor("#0b0b0b"),
            leading=16,
            leftIndent=20,
        ),
        "footnote": ParagraphStyle(
            "footnote",
            fontName="Noto",
            fontSize=8,
            textColor=colors.HexColor("#898781"),
        ),
        "tag": ParagraphStyle(
            "tag",
            fontName="Noto",
            fontSize=9,
            textColor=colors.HexColor("#52514e"),
        ),
        "badge_blue": ParagraphStyle(
            "badge_blue",
            fontName="Noto",
            fontSize=8.5,
            textColor=colors.HexColor("#185fa5"),
        ),
        "badge_gray": ParagraphStyle(
            "badge_gray",
            fontName="Noto",
            fontSize=8.5,
            textColor=colors.HexColor("#52514e"),
        ),
        "statlabel": ParagraphStyle(
            "statlabel",
            fontName="Noto",
            fontSize=8,
            textColor=colors.HexColor("#898781"),
        ),
        "statvalue": ParagraphStyle(
            "statvalue",
            fontName="NotoBold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0b0b0b"),
        ),
        "statsub": ParagraphStyle(
            "statsub",
            fontName="Noto",
            fontSize=8,
            textColor=colors.HexColor("#185fa5"),
        ),
        "statsub_muted": ParagraphStyle(
            "statsub_muted",
            fontName="Noto",
            fontSize=8,
            textColor=colors.HexColor("#898781"),
        ),
        "statlabel_g": ParagraphStyle(
            "statlabel_g",
            fontName="Noto",
            fontSize=8,
            textColor=colors.HexColor("#3b6d11"),
        ),
        "statvalue_g": ParagraphStyle(
            "statvalue_g",
            fontName="NotoBold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#3b6d11"),
        ),
    }


def generate_fable_pdf(data: dict, output_path: str, radar_tmp_path: str | None = None) -> str:
    """채점·메타 dict → PDF 파일. 반환값은 output_path."""
    _ensure_fonts()
    stats = compute_structure_stats(data["body_text"], data["characters"])

    radar_owned = False
    if radar_tmp_path is None:
        radar_fd, radar_tmp_path = tempfile.mkstemp(suffix="_radar.png")
        # mkstemp는 fd를 열어 두므로 닫은 뒤 matplotlib가 덮어쓴다
        os.close(radar_fd)
        radar_owned = True

    try:
        make_radar_chart(
            data["fun"],
            data["violence"],
            data["moral_clarity"],
            data["ending_tone"],
            radar_tmp_path,
        )

        s = _styles()
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=22 * mm,
            rightMargin=22 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )
        flow = []

        flow.append(Paragraph("이솝우화 도감 · 분석 카드", s["eyebrow"]))

        badge_tbl = Table(
            [
                [
                    Paragraph(f"이솝우화 #{data['id']}", s["badge_blue"]),
                    Paragraph(f"결말톤: {data['ending_tone']}", s["badge_gray"]),
                ]
            ],
            colWidths=[28 * mm, 28 * mm],
        )
        badge_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#E6F1FB")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F1EFE8")),
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
        flow.append(Paragraph(str(data["title"]), s["title"]))
        flow.append(Paragraph(str(data["subtitle"]), s["subtitle"]))

        flow.append(Paragraph("내용 평가", s["section"]))
        ending = data["ending_tone"]
        eval_tbl = Table(
            [
                ["재미도", f"{data['fun']} / 5"],
                ["폭력성", f"{data['violence']} / 5"],
                ["교훈 명확도", f"{data['moral_clarity']} / 5"],
                ["결말톤", f"{ending} ({ENDING_TONE_SCORE.get(ending, 3)} / 5)"],
            ],
            colWidths=[35 * mm, 30 * mm],
        )
        eval_tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Noto"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#52514e")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e1e0d9")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        radar_img = Image(radar_tmp_path, width=50 * mm, height=44 * mm)
        combo = Table([[eval_tbl, radar_img]], colWidths=[75 * mm, 80 * mm])
        combo.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("LEFTPADDING", (1, 0), (1, 0), 18),
                ]
            )
        )
        flow.append(combo)
        flow.append(Spacer(1, 4))

        flow.append(Paragraph("키워드", s["section"]))
        tags = list(data.get("tags") or ["우화"])
        tag_cells = [Paragraph(str(t), s["tag"]) for t in tags]
        tags_tbl = Table([tag_cells], colWidths=[30 * mm] * len(tag_cells))
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

        flow.append(Paragraph("영상화 적합도 (글자수 기반 자동 계산)", s["section"]))

        def stat_cell(label, value, sub, sub_style):
            return Table(
                [
                    [Paragraph(label, s["statlabel"])],
                    [Paragraph(value, s["statvalue"])],
                    [Paragraph(sub, sub_style)],
                ],
                colWidths=[30 * mm],
            )

        stats_tbl = Table(
            [
                [
                    stat_cell(
                        "예상 낭독시간",
                        f"{stats['reading_seconds']}초",
                        stats["shorts_label"],
                        s["statsub"],
                    ),
                    stat_cell(
                        "등장인물",
                        f"{len(data['characters'])}명",
                        stats["difficulty_label"],
                        s["statsub"],
                    ),
                    stat_cell(
                        "대사비중",
                        f"{stats['dialogue_ratio']}%",
                        stats["dialogue_label"],
                        s["statsub"],
                    ),
                    stat_cell(
                        "분량",
                        f"{stats['char_count']}자",
                        f"{stats['expected_pages']}p 분량",
                        s["statsub_muted"],
                    ),
                    stat_cell("최종평가", stats["final_grade"], "", s["statlabel_g"]),
                ]
            ],
            colWidths=[32 * mm] * 5,
        )
        stats_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (3, 0), colors.HexColor("#F1EFE8")),
                    ("BACKGROUND", (4, 0), (4, 0), colors.HexColor("#EAF3DE")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        stats_tbl.hAlign = "LEFT"
        flow.append(stats_tbl)
        flow.append(Spacer(1, 10))

        flow.append(Paragraph("원문", s["section"]))
        origin_lines = [ln.strip() for ln in str(data["body_text"]).split("\n") if ln.strip()]
        # reportlab Paragraph는 < > 를 태그로 해석 → 이스케이프
        origin_html = "<br/>".join(
            ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for ln in origin_lines
        )
        flow.append(Paragraph(origin_html, s["body_indent"]))
        flow.append(Spacer(1, 8))

        flow.append(Paragraph("한마디 결론", s["section"]))
        modern = str(data.get("modern_take") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        modern_box = Table([[Paragraph(modern, s["body"])]], colWidths=[155 * mm])
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
        flow.append(Spacer(1, 10))

        flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e1e0d9")))
        flow.append(Spacer(1, 4))
        source_note = str(data.get("source_note") or "")
        flow.append(Paragraph(f"※ 원문 출처: {source_note}", s["footnote"]))

        doc.build(flow)
        return output_path
    finally:
        if radar_owned and radar_tmp_path:
            try:
                Path(radar_tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
