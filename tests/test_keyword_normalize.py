"""키워드 한글 정규화 단위 테스트."""

from app.fable_pdf.keyword_normalize import normalize_keyword_tags


def test_hanja_only_tag_mapped_to_hangul() -> None:
    assert normalize_keyword_tags(["貪欲", "무지", "결과"]) == ["탐욕", "무지", "결과"]


def test_pure_hanja_unknown_dropped() -> None:
    assert normalize_keyword_tags(["未知漢字"]) == ["우화"]


def test_empty_falls_back() -> None:
    assert normalize_keyword_tags([]) == ["우화"]
    assert normalize_keyword_tags(None) == ["우화"]


def test_empty_fallback_none_returns_empty() -> None:
    """커스텀 경로는 우화 폴백을 쓰지 않는다."""
    assert normalize_keyword_tags([], empty_fallback=None) == []
    assert normalize_keyword_tags(None, empty_fallback=None) == []


def test_mixed_strips_cjk() -> None:
    assert normalize_keyword_tags(["탐욕貪欲"]) == ["탐욕"]
