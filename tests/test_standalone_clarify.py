"""단독 애매어(해석/결론/mbti) → 되묻기 (검색·Groq 금지)."""

from app.metrics.vague import try_clarify_vague_question


TITLES = ["늑대와 어린양"]


def test_standalone_해석_clarifies() -> None:
    result = try_clarify_vague_question("해석", known_titles=TITLES)
    assert result is not None
    assert "어떤 걸 알고 싶으신가요" in result["answer"]
    assert "유형별 해석" in result["answer"]
    assert result["citations"] == []


def test_standalone_결론_clarifies() -> None:
    result = try_clarify_vague_question("결론", known_titles=TITLES)
    assert result is not None
    assert "어떤 걸 알고 싶으신가요" in result["answer"]


def test_standalone_mbti_clarifies() -> None:
    result = try_clarify_vague_question("mbti", known_titles=TITLES)
    assert result is not None
    assert "어떤 걸 알고 싶으신가요" in result["answer"]
    # MBTI 설정 안내와 혼동되면 안 됨
    assert "저장했습니다" not in result["answer"]


def test_한마디_결론_with_title_not_standalone() -> None:
    """제목+트리거는 vague가 가로채지 않음 → verbatim 경로."""
    assert (
        try_clarify_vague_question("늑대와 어린양 한마디 결론", known_titles=TITLES)
        is None
    )
