"""짧은·애매 질문 → 되묻기 (검색·Groq 요약 단정 금지)."""

from app.metrics.vague import try_clarify_vague_question


TITLES = ["늑대와 어린양"]


def test_c1_single_word_wolf_clarifies() -> None:
    """C1: 「늑대」만 → 되묻기, 줄거리 요약 아님."""
    result = try_clarify_vague_question("늑대", known_titles=TITLES)
    assert result is not None
    assert "어떤 우화" in result["answer"]
    assert result["citations"] == []
    assert "잡아먹" not in result["answer"]


def test_c2_who_are_you_not_vague() -> None:
    """C2: 「너 누구야」는 그래프(Tool 0)로 보냄."""
    assert try_clarify_vague_question("너 누구야", known_titles=TITLES) is None
    assert try_clarify_vague_question("너는 누구야?", known_titles=TITLES) is None


def test_title_question_not_vague() -> None:
    """제목이 들어 있으면 되묻기하지 않음."""
    assert (
        try_clarify_vague_question("늑대와 어린양 줄거리 알려줘", known_titles=TITLES)
        is None
    )


def test_metric_style_left_to_metric_router() -> None:
    """지표 문구는 vague에서 가로채지 않음 (metric 라우터가 처리)."""
    assert try_clarify_vague_question("내용평가는", known_titles=TITLES) is None


def test_박쥐_lists_matching_titles() -> None:
    """짧은 「박쥐」→ 되묻기 + 제목에 박쥐가 들어간 목록."""
    titles = ["박쥐와 족제비", "박쥐와 쥐들", "늑대와 어린양"]
    result = try_clarify_vague_question("박쥐", known_titles=titles)
    assert result is not None
    answer = result["answer"]
    assert "어떤 우화를 말씀하시나요?" in answer
    assert "「박쥐」가 들어간 제목:" in answer
    assert "1. 박쥐와 족제비" in answer
    assert "2. 박쥐와 쥐들" in answer
    assert "늑대와 어린양" not in answer
    assert "\n1. " in answer and "\n2. " in answer


def test_vague_without_matching_title_keeps_generic_clarify() -> None:
    result = try_clarify_vague_question("여우", known_titles=["늑대와 어린양"])
    assert result is not None
    assert "여우」가 들어간 제목" not in result["answer"]
    assert "제목이나 알고 싶은 내용" in result["answer"]
