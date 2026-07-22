"""우화 분석 카드 — metadata 파싱 + origin/modern 청크 분리 (TDD)."""

from pathlib import Path

from ingest.chunk import chunk_pages
from ingest.fable_parse import parse_fable_card
from ingest.load_pdf import PdfPage

FIXTURE_TEXT = (
    Path(__file__).parent / "fixtures" / "fable_card_sample.txt"
).read_text(encoding="utf-8")


def test_parse_fable_card_extracts_score_fields() -> None:
    """재미도·폭력성·교훈·키워드 등 구조화 필드가 기대값과 일치한다."""
    parsed = parse_fable_card(FIXTURE_TEXT)

    assert parsed is not None
    assert parsed["fable_id"] == 1
    assert parsed["title"] == "늑대와 어린양"
    assert parsed["ending_tone"] == "새드"
    assert parsed["fun"] == 2
    assert parsed["violence"] == 3
    assert parsed["moral_clarity"] == 5
    assert parsed["keywords"] == ["권력남용", "자기합리화", "부당함"]
    assert parsed["reading_seconds"] == 88
    assert parsed["characters_count"] == 2
    assert parsed["dialogue_ratio"] == 43
    assert parsed["char_count"] == 469
    assert parsed["final_grade"] == "보통"


def test_parse_fable_card_splits_origin_and_modern() -> None:
    """원문 / 오늘날로 치면 본문을 분리하고 출처 ※ 줄은 modern에서 뺀다."""
    parsed = parse_fable_card(FIXTURE_TEXT)

    assert parsed is not None
    assert "늑대가 양떼무리에서" in parsed["origin_text"]
    assert "오늘날로 치면" not in parsed["origin_text"]
    assert "상사가 트집" in parsed["modern_text"]
    assert "※" not in parsed["modern_text"]
    assert "재미도" not in parsed["origin_text"]


def test_parse_fable_card_splits_한마디_결론_label() -> None:
    """새 라벨 「한마디 결론」도 modern으로 분리한다."""
    text = FIXTURE_TEXT.replace("오늘날로 치면", "한마디 결론")
    parsed = parse_fable_card(text)

    assert parsed is not None
    assert "한마디 결론" not in parsed["origin_text"]
    assert "상사가 트집" in parsed["modern_text"]
    assert "※" not in parsed["modern_text"]


def test_parse_fable_card_returns_none_for_plain_text() -> None:
    """우화 카드 라벨이 없으면 None → 일반 청킹 경로."""
    assert parse_fable_card("춘향은 이몽룡과 백년가약을 맺었다.") is None


def test_chunk_pages_fable_attaches_metadata_and_content_types() -> None:
    """우화 PDF 텍스트는 origin/modern 청크로 나뉘고 metadata가 붙는다."""
    pages = [
        PdfPage(text=FIXTURE_TEXT, source_file="01_늑대와 어린양.pdf", page=1),
    ]

    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=60)

    types = {chunk.metadata["content_type"] for chunk in chunks}
    assert types == {"origin", "modern"}

    for chunk in chunks:
        assert chunk.metadata["fable_id"] == 1
        assert chunk.metadata["fun"] == 2
        assert chunk.metadata["keywords"] == "권력남용|자기합리화|부당함"
        assert "재미도" not in chunk.page_content
        assert "2 / 5" not in chunk.page_content

    origin_text = " ".join(
        c.page_content for c in chunks if c.metadata["content_type"] == "origin"
    )
    modern_text = " ".join(
        c.page_content for c in chunks if c.metadata["content_type"] == "modern"
    )
    assert "늑대가" in origin_text
    assert "상사" in modern_text


def test_chunk_pages_plain_pdf_has_no_fable_fields() -> None:
    """일반 텍스트는 우화 metadata 없이 기존처럼 청킹된다."""
    pages = [
        PdfPage(
            text="짧은 문장입니다. 그리고 이어지는 문장입니다.",
            source_file="plain.pdf",
            page=1,
        ),
    ]

    chunks = chunk_pages(pages, chunk_size=40, chunk_overlap=10)

    assert len(chunks) >= 1
    assert "content_type" not in chunks[0].metadata
    assert "fable_id" not in chunks[0].metadata


def test_load_and_chunk_real_fable_pdf_if_present() -> None:
    """uploads의 01_ 샘플 PDF가 있으면 origin/modern + fun 메타가 붙는다."""
    from ingest.load_pdf import load_pdf_pages

    uploads = Path(__file__).resolve().parents[1] / "data" / "uploads"
    pdfs = sorted(uploads.glob("01_*.pdf"))
    if not pdfs:
        return

    pages = load_pdf_pages(pdfs[0])
    # 로더가 줄바꿈을 유지해야 라벨 파싱이 된다
    assert "\n" in pages[0].text

    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=60)
    assert {c.metadata.get("content_type") for c in chunks} == {"origin", "modern"}
    assert chunks[0].metadata["fun"] == 2
    assert "권력남용" in chunks[0].metadata["keywords"]
