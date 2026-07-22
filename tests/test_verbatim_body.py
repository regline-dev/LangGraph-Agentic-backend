"""원문 / 오늘날로 치면 — 본문 그대로 (Groq 요약 금지)."""

from __future__ import annotations

from typing import Any

from app.metrics.memory import FableSessionMemory
from app.metrics.verbatim import try_handle_verbatim_body

ORIGIN = (
    "늑대가 어린양을 만났어요.\n"
    "그러자 늑대는 다짜고짜 어린양을 움켜잡더니 꿀꺽 잡아먹어버리더니 말했어요.\n"
    '"네가 내 말에 아무리 논박을 해도, 저녁식사를 내가 마다할 리야 없지."\n'
    "악당은 언제나 자신들의 악행에 대해 그럴듯한 구실을 찾는 법이랍니다."
)
MODERN = "상사가 트집 잡아 부당해고하는 상황이라 할 수 있다."

TITLES = ["늑대와 어린양"]


def _fetch(title: str, content_type: str) -> dict[str, Any] | None:
    if title != "늑대와 어린양":
        return None
    if content_type == "origin":
        return {
            "text": ORIGIN,
            "citations": [
                {"source_file": "01_늑대와 어린양.pdf", "page": 1, "snippet": ORIGIN[:80]}
            ],
        }
    if content_type == "modern":
        return {
            "text": MODERN,
            "citations": [
                {"source_file": "01_늑대와 어린양.pdf", "page": 2, "snippet": MODERN[:80]}
            ],
        }
    return None


def test_b1b_origin_returns_verbatim_including_moral() -> None:
    """원문은 → 교훈 문장까지 그대로."""
    result = try_handle_verbatim_body(
        "늑대와 어린양의 원문은",
        session_id="s1",
        memory=FableSessionMemory(),
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert "악당은 언제나" in result["answer"]
    assert "저녁식사" in result["answer"]
    # 요약체가 섞이면 안 됨 (재작성 금지)
    assert "요약하면" not in result["answer"]


def test_b2_modern_returns_verbatim() -> None:
    result = try_handle_verbatim_body(
        "늑대와 어린양 오늘날로 치면",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert result["answer"] == MODERN


def test_줄거리_returns_origin_verbatim() -> None:
    """줄거리도 원문 본문 그대로 (LLM 요약 금지)."""
    result = try_handle_verbatim_body(
        "늑대와 어린양 줄거리 알려줘",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert result["answer"] == ORIGIN
    assert "악당은 언제나" in result["answer"]


def test_내용은_returns_origin_verbatim() -> None:
    result = try_handle_verbatim_body(
        "늑대와 어린양의 내용은",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert result["answer"] == ORIGIN


def test_origin_without_title_clarifies() -> None:
    result = try_handle_verbatim_body(
        "원문은",
        session_id=None,
        memory=FableSessionMemory(),
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert "어떤 우화" in result["answer"]


def test_origin_uses_short_term_memory() -> None:
    memory = FableSessionMemory()
    memory.set("s2", "늑대와 어린양")
    result = try_handle_verbatim_body(
        "원문은",
        session_id="s2",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert "악당은 언제나" in result["answer"]
