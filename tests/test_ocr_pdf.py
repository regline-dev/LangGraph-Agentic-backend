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
