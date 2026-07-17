"""PDF 로드 — 페이지별 텍스트 추출."""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class PdfPage:
    """PDF 한 페이지의 텍스트와 출처."""

    text: str
    source_file: str
    page: int  # 1-based


def load_pdf_pages(pdf_path: Path | str) -> list[PdfPage]:
    """PDF 파일을 읽어 페이지 리스트를 반환한다.

    Args:
        pdf_path: PDF 파일 경로

    Raises:
        FileNotFoundError: 파일이 없을 때
        ValueError: PDF가 아니거나 페이지 텍스트를 전혀 못 읽을 때
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일이 없습니다: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"PDF 확장자가 아닙니다: {path}")

    reader = PdfReader(str(path))
    source_file = path.name
    pages: list[PdfPage] = []

    for index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = " ".join(raw_text.split())
        if text:
            pages.append(PdfPage(text=text, source_file=source_file, page=index))

    if not pages:
        raise ValueError(f"추출 가능한 텍스트가 없습니다: {path}")

    return pages
