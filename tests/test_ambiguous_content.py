"""내용·줄거리는 verbatim 원문 경로 — vague가 가로채지 않음."""

from app.metrics.vague import try_clarify_vague_question

TITLES = ["박쥐와 족제비", "늑대와 어린양"]


def test_내용은_left_to_verbatim() -> None:
    assert (
        try_clarify_vague_question("박쥐와 족제비의 내용은", known_titles=TITLES)
        is None
    )


def test_줄거리_left_to_verbatim() -> None:
    assert (
        try_clarify_vague_question("늑대와 어린양 줄거리", known_titles=TITLES)
        is None
    )


def test_내용평가_not_caught_by_vague() -> None:
    assert try_clarify_vague_question("내용평가는", known_titles=TITLES) is None
