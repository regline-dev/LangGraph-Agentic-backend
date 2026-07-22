"""제목만 입력 → 카드 전체(문서 기반, LLM 없음)."""

from __future__ import annotations

from typing import Any

from app.metrics.memory import FableSessionMemory
from app.metrics.title_card import try_handle_title_only_full_card

ORIGIN = "박쥐가 족제비에게 붙잡혔어요.\n이렇듯 처신해야한답니다."
MODERN = "상황 봐가며 처신하는 스킬."

META = {
    "title": "박쥐와 족제비",
    "fun": 3,
    "violence": 2,
    "moral_clarity": 5,
    "ending_tone": "해피",
    "keywords": ["처세술", "변신", "생존"],
    "final_grade": "보통",
}


def _fetch(title: str, content_type: str) -> dict[str, Any] | None:
    if title != "박쥐와 족제비":
        return None
    if content_type == "origin":
        return {
            "text": ORIGIN,
            "citations": [{"source_file": "02.pdf", "page": 1, "snippet": "박쥐"}],
        }
    if content_type == "modern":
        return {
            "text": MODERN,
            "citations": [{"source_file": "02.pdf", "page": 2, "snippet": "처신"}],
        }
    return None


def _lookup(title: str) -> dict[str, Any] | None:
    if title == "박쥐와 족제비":
        return dict(META)
    return None


def test_title_only_returns_full_card() -> None:
    memory = FableSessionMemory()
    result = try_handle_title_only_full_card(
        "박쥐와 족제비",
        session_id="s1",
        memory=memory,
        known_titles=["박쥐와 족제비"],
        lookup_fn=_lookup,
        fetch_fn=_fetch,
    )
    assert result is not None
    answer = result["answer"]
    assert "박쥐와 족제비" in answer
    assert ORIGIN in answer
    assert MODERN in answer
    assert "재미도" in answer and "3" in answer
    assert "처세술" in answer
    assert memory.get_title("s1") == "박쥐와 족제비"
    assert result["citations"]


def test_title_with_내용_not_full_card() -> None:
    """내용 트리거는 verbatim — full card 아님."""
    assert (
        try_handle_title_only_full_card(
            "박쥐와 족제비의 내용은",
            session_id=None,
            memory=FableSessionMemory(),
            known_titles=["박쥐와 족제비"],
            lookup_fn=_lookup,
            fetch_fn=_fetch,
        )
        is None
    )
