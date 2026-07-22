"""MBTI 재해석 — 톤 맵 없이 MBTI+한마디+분량 제약만."""

from __future__ import annotations

from typing import Any

from app.metrics import mbti_reinterpret as mod
from app.metrics.mbti_reinterpret import reinterpret_fable_for_mbti


def test_no_tone_map_helpers() -> None:
    """유형별 고정 톤/랜덤 API는 쓰지 않는다."""
    assert not hasattr(mod, "tone_for_mbti")
    assert not hasattr(mod, "pick_reinterpret_tone")
    assert not hasattr(mod, "MBTI_TONES")


def test_reinterpret_prompt_is_mbti_and_modern_and_length() -> None:
    captured: dict[str, Any] = {}

    class _FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            captured["messages"] = kwargs["messages"]

            class _Msg:
                content = "짧은 한 줄. 또 한 줄."

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    answer = reinterpret_fable_for_mbti(
        title="박쥐와 족제비",
        origin_text="원문 일부",
        modern_text="상황 봐가며 태세전환.",
        mbti="INFP",
        client=_FakeClient(),
        api_key="dummy",
    )
    system = captured["messages"][0]["content"]
    user = captured["messages"][1]["content"]
    assert "70자" in system and "두 문장" in system
    assert "INFP" in user
    assert "한마디 결론" in user
    assert "상황 봐가며" in user
    assert "유머" not in system and "시적" not in system and "지정 톤" not in user
    assert "[INFP 유형별 해석]" in answer
    assert "· 유머" not in answer and "· 시적" not in answer
