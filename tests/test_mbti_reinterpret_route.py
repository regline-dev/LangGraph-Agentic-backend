"""MBTI 있을 때 유형별 해석 / 없을 때 modern 그대로."""

from __future__ import annotations

from typing import Any

from app.metrics.memory import FableSessionMemory
from app.metrics.verbatim import try_handle_verbatim_body

ORIGIN = "늑대가 어린양을 만났어요.\n악당은 언제나 구실을 찾는 법이랍니다."
MODERN = "상사가 트집 잡아 부당해고하는 상황."

TITLES = ["늑대와 어린양"]


def _fetch(title: str, content_type: str) -> dict[str, Any] | None:
    if title != "늑대와 어린양":
        return None
    if content_type == "origin":
        return {"text": ORIGIN, "citations": [{"source_file": "a.pdf", "page": 1, "snippet": ""}]}
    if content_type == "modern":
        return {"text": MODERN, "citations": [{"source_file": "a.pdf", "page": 2, "snippet": ""}]}
    return None


def _fake_llm(**kwargs: Any) -> str:
    return f"FAKE-{kwargs['mbti']}:{kwargs['title']}"


def test_modern_without_mbti_returns_card_text() -> None:
    memory = FableSessionMemory()
    result = try_handle_verbatim_body(
        "늑대와 어린양 재해석",
        session_id="s1",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
        reinterpret_fn=_fake_llm,
    )
    assert result is not None
    assert result["answer"] == MODERN
    assert result["citations"]


def test_modern_with_mbti_uses_llm() -> None:
    memory = FableSessionMemory()
    memory.set_mbti("s1", "INFP")
    result = try_handle_verbatim_body(
        "늑대와 어린양 MBTI 유형별 해석",
        session_id="s1",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
        reinterpret_fn=_fake_llm,
    )
    assert result is not None
    assert result["answer"] == "FAKE-INFP:늑대와 어린양"
    assert result["citations"] == []


def test_natural_mbti로_해석해줘_with_mbti_uses_llm() -> None:
    """자연어 「MBTI로 해석해줘」도 유형별 재해석."""
    memory = FableSessionMemory()
    memory.set_mbti("s1", "INFP")
    result = try_handle_verbatim_body(
        "늑대와 어린양 MBTI로 해석해줘",
        session_id="s1",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
        reinterpret_fn=_fake_llm,
    )
    assert result is not None
    assert result["answer"] == "FAKE-INFP:늑대와 어린양"


def test_keyword_한마디_결론_is_modern() -> None:
    memory = FableSessionMemory()
    result = try_handle_verbatim_body(
        "늑대와 어린양 한마디 결론",
        session_id=None,
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert result["answer"] == MODERN


def test_keyword_오늘날로_치면_still_modern() -> None:
    memory = FableSessionMemory()
    result = try_handle_verbatim_body(
        "늑대와 어린양 오늘날로 치면",
        session_id=None,
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert result["answer"] == MODERN
