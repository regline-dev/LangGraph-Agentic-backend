"""배치(layout) 가로 카드 · 세로 리스트 분기 테스트."""

from __future__ import annotations

from pathlib import Path

from app.fable_pdf.pdf_generator import _styles
from app.fable_pdf.typed_pdf import (
    TYPED_CONTENT_WIDTH,
    build_group_table,
    generate_typed_pdf,
    typed_section_style,
)


def test_vertical_layout_is_label_value_rows() -> None:
    """리스트형(세로): 라벨|값 행이 필드 수만큼."""
    s = _styles()
    fields = {"우천시": "정상", "금지사항": "주류 금지", "문의처": "02-1234"}
    tbl = build_group_table(fields, layout="vertical", styles=s)
    assert len(tbl._argW) == 2  # 2 columns
    assert tbl._nrows == 3


def test_horizontal_layout_is_single_row_cards() -> None:
    """카드형(가로): 필드가 한 행의 카드 셀로 나란히."""
    s = _styles()
    fields = {"우천시": "정상", "금지사항": "주류 금지", "문의처": "02-1234"}
    tbl = build_group_table(fields, layout="horizontal", styles=s)
    assert tbl._nrows == 1
    assert tbl._ncols == 3


def test_horizontal_cards_fill_full_content_width_for_3_and_4() -> None:
    """3개·4개 모두 본문 가로폭(TYPED_CONTENT_WIDTH)을 꽉 채운다."""
    s = _styles()
    for n in (3, 4):
        fields = {f"항목{i}": f"값{i}" for i in range(1, n + 1)}
        tbl = build_group_table(fields, layout="horizontal", styles=s)
        total = sum(tbl._argW)
        assert abs(total - TYPED_CONTENT_WIDTH) < 0.5, f"n={n} total={total}"
        for w in tbl._argW:
            assert abs(w - TYPED_CONTENT_WIDTH / n) < 0.5


def test_typed_section_title_is_smaller_than_default_section() -> None:
    """이용 안내 등 섹션 제목은 기본 section(9.5)보다 작다."""
    default = _styles()["section"]
    typed = typed_section_style()
    assert typed.fontSize < default.fontSize
    assert typed.fontSize <= 8


def test_generate_typed_pdf_respects_group_layouts(tmp_path: Path) -> None:
    """group_layouts=horizontal 인 그룹도 PDF 파일로 출력된다."""
    out = tmp_path / "layout.pdf"
    generate_typed_pdf(
        {
            "id": 18,
            "title": "한강별빛축제",
            "body_text": "본문",
            "source_note": "테스트",
            "type_name": "지방축제 안내",
            "groups": {
                "기본 정보": {"축제명": "한강별빛축제"},
                "이용 안내": {
                    "우천시": "소나기 정상",
                    "금지사항": "주류 금지",
                    "문의처": "02-1234",
                },
            },
            "group_layouts": {
                "기본 정보": "vertical",
                "이용 안내": "horizontal",
            },
            "subtitles": {},
            "tags": [],
        },
        str(out),
    )
    assert out.is_file() and out.stat().st_size > 500
