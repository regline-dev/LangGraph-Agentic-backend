"""청킹 — 규칙 기반(일방향 Default A) 고정 길이 분할."""

from dataclasses import dataclass
from pathlib import Path

from ingest.load_pdf import PdfPage


@dataclass(frozen=True)
class DocumentChunk:
    """Vector Store에 넣을 청크 (README §5.2 스키마)."""

    page_content: str
    metadata: dict[str, str | int]


def chunk_pages(
    pages: list[PdfPage],
    chunk_size: int = 200,
    chunk_overlap: int = 40,
) -> list[DocumentChunk]:
    """페이지 텍스트를 고정 길이로 나누고 metadata를 붙인다.

    Args:
        pages: load_pdf_pages 결과
        chunk_size: 청크 최대 글자 수
        chunk_overlap: 인접 청크 겹침 글자 수

    Raises:
        ValueError: 잘못된 청크 설정 또는 빈 입력
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size는 1 이상이어야 합니다.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap은 0 이상이고 chunk_size보다 작아야 합니다.")
    if not pages:
        raise ValueError("청킹할 페이지가 없습니다.")

    chunks: list[DocumentChunk] = []
    sequence = 1

    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                stem = Path(page.source_file).stem
                chunk_id = f"{stem}-{sequence:03d}"
                chunks.append(
                    DocumentChunk(
                        page_content=piece,
                        metadata={
                            "source_file": page.source_file,
                            "page": page.page,
                            "chunk_id": chunk_id,
                        },
                    )
                )
                sequence += 1

            if end >= len(text):
                break
            start = end - chunk_overlap

    if not chunks:
        raise ValueError("생성된 청크가 없습니다.")

    return chunks
