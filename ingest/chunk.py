"""청킹 — Separator 우선 분할 (일방향 Default A).

이솝 우화 분석 카드는 fable_parse로 metadata/본문을 분리한 뒤 청킹한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest.fable_parse import parse_fable_card
from ingest.load_pdf import PdfPage

# 우선순위: 문단 → 줄 → 문장부호(뒤 공백) → 공백 → 글자 hard cut
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", "? ", "! ", "。", " ", "")

_FABLE_META_KEYS: tuple[str, ...] = (
    "fable_id",
    "title",
    "ending_tone",
    "fun",
    "violence",
    "moral_clarity",
    "reading_seconds",
    "characters_count",
    "dialogue_ratio",
    "char_count",
    "final_grade",
    "keywords",
)


@dataclass(frozen=True)
class DocumentChunk:
    """Vector Store에 넣을 청크 (README §5.2 스키마)."""

    page_content: str
    metadata: dict[str, Any]


def chunk_pages(
    pages: list[PdfPage],
    # chunk_size / overlap = 글자 수 (토큰 아님).
    # 문서 종류별 분기는 아직 미적용 — 나중에 doc_type 넣으면 후보값:
    #   manual   → 500 / 100
    #   contract → 800 / 150
    #   default  → 300 / 60
    chunk_size: int = 300,
    chunk_overlap: int = 60,
) -> list[DocumentChunk]:
    """페이지 텍스트를 Separator 우선으로 나누고 metadata를 붙인다.

    우화 분석 카드면 페이지를 이어 붙여 파싱 후 origin/modern만 청킹한다.

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

    joined = "\n".join(page.text for page in pages if page.text and page.text.strip())
    fable = parse_fable_card(joined)
    if fable is not None:
        return _chunk_fable_pages(
            pages,
            fable=fable,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    return _chunk_plain_pages(
        pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def _chunk_fable_pages(
    pages: list[PdfPage],
    *,
    fable: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    """원문/현대 본문만 청킹하고 우화 metadata를 동일하게 붙인다."""
    source_file = pages[0].source_file
    stem = Path(source_file).stem
    base_meta = _fable_metadata_for_payload(fable)

    sections: list[tuple[str, str, int]] = [
        ("origin", fable["origin_text"], pages[0].page),
    ]
    modern = (fable.get("modern_text") or "").strip()
    if modern:
        # 현대 본문이 뒤 페이지에 있어도 content_type으로 구분 (page는 마지막 페이지 힌트)
        sections.append(("modern", modern, pages[-1].page))

    chunks: list[DocumentChunk] = []
    sequence = 1
    for content_type, body, page_no in sections:
        pieces = _split_text(body, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for piece in pieces:
            chunk_id = f"{stem}-{sequence:03d}"
            metadata: dict[str, Any] = {
                "source_file": source_file,
                "page": page_no,
                "chunk_id": chunk_id,
                "content_type": content_type,
                **base_meta,
            }
            chunks.append(DocumentChunk(page_content=piece, metadata=metadata))
            sequence += 1

    if not chunks:
        raise ValueError("생성된 청크가 없습니다.")
    return chunks


def _fable_metadata_for_payload(fable: dict[str, Any]) -> dict[str, Any]:
    """Qdrant/청크용 — keywords는 '|' join 문자열."""
    meta: dict[str, Any] = {}
    for key in _FABLE_META_KEYS:
        value = fable[key]
        if key == "keywords":
            meta[key] = "|".join(value) if isinstance(value, list) else str(value)
        else:
            meta[key] = value
    return meta


def _chunk_plain_pages(
    pages: list[PdfPage],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    """일반 PDF — 페이지 단위 Separator 청킹."""
    chunks: list[DocumentChunk] = []
    sequence = 1

    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        pieces = _split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for piece in pieces:
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

    if not chunks:
        raise ValueError("생성된 청크가 없습니다.")

    return chunks


def _split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """한 페이지 텍스트를 청크 리스트로 나눈다."""
    raw_parts = _recursive_split(text, chunk_size=chunk_size, separators=_SEPARATORS)
    return _merge_with_overlap(raw_parts, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def _recursive_split(
    text: str,
    *,
    chunk_size: int,
    separators: tuple[str, ...],
) -> list[str]:
    """Separator 우선으로 chunk_size 이하 조각으로 나눈다."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    if not separators:
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    separator = separators[0]
    next_separators = separators[1:]

    # 빈 separator = 글자 단위 hard cut
    if separator == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(separator)
    good_splits: list[str] = []
    for index, part in enumerate(parts):
        # 분리자는 앞 조각 끝에 붙인다 (문장부호·줄바꿈 보존)
        piece = part + separator if index < len(parts) - 1 else part
        if not piece:
            continue
        if len(piece) <= chunk_size:
            good_splits.append(piece)
        else:
            good_splits.extend(
                _recursive_split(
                    piece,
                    chunk_size=chunk_size,
                    separators=next_separators,
                )
            )
    return good_splits


def _merge_with_overlap(
    parts: list[str],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """작은 조각을 chunk_size까지 합치고, 다음 청크에 overlap을 붙인다."""
    if not parts:
        return []

    merged: list[str] = []
    current = ""

    for part in parts:
        candidate = f"{current}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current.strip():
            merged.append(current.strip())
            # 다음 청크 시작: 이전 청크 꼬리 + 이번 조각
            overlap_prefix = current[-chunk_overlap:] if chunk_overlap else ""
            current = f"{overlap_prefix}{part}"
            # 겹침+조각이 여전히 너무 길면 Separator 없이 hard cut
            if len(current) > chunk_size:
                hard = _hard_cut_with_overlap(
                    current,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                merged.extend(hard[:-1])
                current = hard[-1] if hard else ""
        else:
            hard = _hard_cut_with_overlap(
                part,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            merged.extend(hard[:-1])
            current = hard[-1] if hard else ""

    if current.strip():
        merged.append(current.strip())

    return merged


def _hard_cut_with_overlap(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """최후 수단: 글자 수 mid-cut + overlap."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = end - chunk_overlap
    return pieces
