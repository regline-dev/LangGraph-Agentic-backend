"""내용평가·키워드 metadata 라우팅 (계획 A1~A10)."""

from __future__ import annotations

from typing import Any

from app.metrics.memory import FableSessionMemory
from app.metrics.route import try_handle_metric_question

SAMPLE_META: dict[str, Any] = {
    "title": "늑대와 어린양",
    "fun": 2,
    "violence": 3,
    "moral_clarity": 5,
    "ending_tone": "새드",
    "keywords": ["권력남용", "자기합리화", "부당함"],
    "final_grade": "보통",
}

TITLES = ["늑대와 어린양"]


def _lookup(title: str) -> dict[str, Any] | None:
    if title == "늑대와 어린양":
        return dict(SAMPLE_META)
    return None


def test_a1_content_eval_with_title_returns_four_scores() -> None:
    """A1: 제목+내용평가 → 4지표, citations 없음."""
    result = try_handle_metric_question(
        "늑대와 어린양의 내용평가는",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert result["citations"] == []
    answer = result["answer"]
    assert "2" in answer and "재미" in answer
    assert "3" in answer and "폭력" in answer
    assert "5" in answer and "교훈" in answer
    assert "새드" in answer


def test_a2_keywords_with_title() -> None:
    """A2: 제목+키워드 → metadata 키워드 목록."""
    result = try_handle_metric_question(
        "늑대와 어린양 키워드는",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert "권력남용" in result["answer"]
    assert "자기합리화" in result["answer"]
    assert "부당함" in result["answer"]
    assert "키워드를 입력해주세요" not in result["answer"]


def test_a7_content_eval_without_context_clarifies() -> None:
    """A7: 맥락 없이 내용평가 → 되묻기."""
    result = try_handle_metric_question(
        "내용평가는",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert "어떤 우화" in result["answer"]
    assert result["citations"] == []


def test_a9_fun_score_uses_short_term_memory() -> None:
    """A9: 직전 우화 메모리 + 재미도는 몇이야 → 2/5."""
    memory = FableSessionMemory()
    memory.set("sess-1", "늑대와 어린양")
    result = try_handle_metric_question(
        "재미도는 몇이야",
        session_id="sess-1",
        memory=memory,
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert "2/5" in result["answer"] or ("2" in result["answer"] and "5" in result["answer"])
    assert "늑대와 어린양" in result["answer"]


def test_a10_fun_score_without_context_clarifies() -> None:
    """A10: 맥락 없이 재미도는 몇이야 → 되묻기."""
    result = try_handle_metric_question(
        "재미도는 몇이야",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert "어떤 우화" in result["answer"]
    assert "재미" in result["answer"]


def test_평가는_alias_uses_short_term_memory() -> None:
    """「평가는」= 내용평가. 단기 메모리 제목으로 4지표."""
    memory = FableSessionMemory()
    memory.set_title("s-eval", "늑대와 어린양")
    result = try_handle_metric_question(
        "평가는",
        session_id="s-eval",
        memory=memory,
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert "재미" in result["answer"]
    assert "2" in result["answer"]
    assert "어떤 우화" not in result["answer"]


def test_최종평가는_not_content_eval() -> None:
    """「최종평가」는 내용평가(4지표)가 아니라 최종등급."""
    from app.metrics.detect import detect_metric_kind

    assert detect_metric_kind("최종평가는") == "final_grade"
    assert detect_metric_kind("평가는") == "content_eval"


def test_a5_content_eval_from_memory_after_title_mention() -> None:
    """A5: 제목 언급 후 내용평가만 → 메모리로 4지표."""
    memory = FableSessionMemory()
    # 제목 포함 비지표 질문으로 메모리에 남김
    first = try_handle_metric_question(
        "늑대와 어린양 줄거리 알려줘",
        session_id="sess-2",
        memory=memory,
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert first is None  # 지표 질문 아님 → 그래프 경로
    assert memory.get("sess-2") == "늑대와 어린양"

    result = try_handle_metric_question(
        "내용평가는",
        session_id="sess-2",
        memory=memory,
        known_titles=TITLES,
        lookup_fn=_lookup,
    )
    assert result is not None
    assert "2" in result["answer"] and "재미" in result["answer"]


def test_non_metric_returns_none_for_graph_path() -> None:
    """일반 질문·자기소개는 metric 라우터가 None → 기존 그래프."""
    memory = FableSessionMemory()
    assert (
        try_handle_metric_question(
            "너 누구야",
            session_id="s",
            memory=memory,
            known_titles=TITLES,
            lookup_fn=_lookup,
        )
        is None
    )
