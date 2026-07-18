"""Groq 판단 연결 — API 호출은 mock으로 검증."""

from unittest.mock import MagicMock

import pytest

from app.graph.groq_decision import make_groq_decide_fn, parse_decision_json


def test_parse_decision_json_need_search_false() -> None:
    raw = '{"need_search": false, "search_query": "", "answer": "안녕하세요. PDF 검색 도우미입니다."}'
    parsed = parse_decision_json(raw)

    assert parsed["need_search"] is False
    assert parsed["answer"].startswith("안녕")
    assert parsed["search_query"] == ""


def test_parse_decision_json_with_markdown_fence() -> None:
    raw = """```json
{"need_search": true, "search_query": "연차 일수", "answer": ""}
```"""
    parsed = parse_decision_json(raw)

    assert parsed["need_search"] is True
    assert parsed["search_query"] == "연차 일수"


def test_parse_decision_json_invalid_raises() -> None:
    with pytest.raises(ValueError, match="JSON"):
        parse_decision_json("not json at all")


def test_make_groq_decide_fn_requires_api_key() -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        make_groq_decide_fn(api_key="", model="llama-3.3-70b-versatile")


def test_make_groq_decide_fn_calls_groq_and_returns_decision() -> None:
    """mock chat completion → decide_fn이 need_search/answer를 반환."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"need_search": false, "search_query": "", "answer": "검색 없이 답합니다."}'
                )
            )
        ]
    )

    decide = make_groq_decide_fn(
        api_key="test-key",
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    result = decide({"question": "너는 누구야?", "observations": [], "tool_call_count": 0})

    assert result["need_search"] is False
    assert "검색" in result["answer"] or "답" in result["answer"]
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "llama-3.3-70b-versatile"
