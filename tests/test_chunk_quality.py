"""청킹 품질 — Separator 우선·overlap·짧은 페이지 (TDD)."""

from ingest.chunk import chunk_pages
from ingest.load_pdf import PdfPage


def _one_page(text: str, source_file: str = "doc.pdf") -> list[PdfPage]:
    return [PdfPage(text=text, source_file=source_file, page=1)]


def test_chunk_prefers_sentence_punctuation_boundary() -> None:
    """문장부호(.) 뒤에서 끊긴다 — 글자 mid-cut으로 다음 문장 중간을 자르지 않는다."""
    # mid-cut(20)이면 첫 청크가 '문'에서 끊김. Separator면 '.' 뒤가 경계.
    text = "짧은 문장입니다. 그리고 이어지는 문장입니다."
    chunks = chunk_pages(_one_page(text), chunk_size=20, chunk_overlap=0)

    assert len(chunks) >= 2
    assert chunks[0].page_content.rstrip().endswith(".")
    assert "그리고" in chunks[1].page_content
    # 첫 청크가 다음 문장 앞글자만 잘라 먹지 않았는지
    assert not chunks[0].page_content.rstrip().endswith("문")


def test_chunk_overlap_shares_adjacent_tail() -> None:
    """인접 청크는 overlap 글자만큼 앞뒤를 공유한다."""
    text = ("가나다라마바사아자차카타파하" * 4) + " " + ("ABCDEFGHIJKLMNOP" * 4)
    chunks = chunk_pages(_one_page(text), chunk_size=40, chunk_overlap=10)

    assert len(chunks) >= 2
    tail = chunks[0].page_content[-10:]
    assert tail in chunks[1].page_content


def test_chunk_short_single_page_stays_one_chunk() -> None:
    """짧은 1페이지는 기본 300/60에서도 청크 1개."""
    text = "짧은 문서입니다."
    chunks = chunk_pages(_one_page(text))

    assert len(chunks) == 1
    assert chunks[0].page_content == text
    assert chunks[0].metadata["chunk_id"] == "doc-001"


def test_default_chunk_params_are_300_and_60() -> None:
    """기본 chunk_size/overlap은 300/60 (글자)."""
    import inspect

    from ingest import chunk as chunk_module

    signature = inspect.signature(chunk_module.chunk_pages)
    assert signature.parameters["chunk_size"].default == 300
    assert signature.parameters["chunk_overlap"].default == 60
