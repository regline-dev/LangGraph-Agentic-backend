"""영수증 PDF 2페이지 동일 품목."""

from io import BytesIO

from pypdf import PdfReader

from app.ocr.pdf import build_receipt_pdf_bytes
from app.tools.ocr_receipt import parse_lines_from_text


def test_receipt_pdf_two_pages_same_items() -> None:
    lines = parse_lines_from_text("A품목 10개 단가 500000원")
    pdf_bytes = build_receipt_pdf_bytes(lines, "receipt")
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 2
    page0 = reader.pages[0].extract_text() or ""
    page1 = reader.pages[1].extract_text() or ""
    assert "A품목" in page0
    assert "A품목" in page1
    assert "공급받는자용" in page0
    assert "공급자용" in page1
    assert "5,000,000" in page0
    assert "5,000,000" in page1


def _supplier_style_cmds():
    from app.ocr.pdf import _supplier_table_style_cmds

    return _supplier_table_style_cmds()


def test_supplier_table_remarks_span_not_split() -> None:
    """비고 값은 한 칸으로 두고, 3열 전체 라벨 배경·GRID로 칸이 갈라지지 않게 한다."""
    cmds = _supplier_style_cmds()
    triples = [(c[0], c[1], c[2]) for c in cmds]
    assert ("SPAN", (2, 5), (4, 5)) in triples
    assert not any(c[0] == "GRID" for c in cmds)
    # (3,0)~(3,-1) 또는 (3,0)~(3,5) 전체를 라벨 배경으로 칠하면 비고 SPAN이 갈라짐
    for cmd in cmds:
        if cmd[0] != "BACKGROUND":
            continue
        start, stop = cmd[1], cmd[2]
        assert not (start == (3, 0) and stop[0] == 3 and stop[1] in (-1, 5))
