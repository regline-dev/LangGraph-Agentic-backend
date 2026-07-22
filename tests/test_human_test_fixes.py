"""사람테스트 P0·P1 — 한마디/목록/MBTI안내/제목부분일치/그대로읽기."""

from __future__ import annotations

from typing import Any

from app.graph.nodes import final_answer_node
from app.metrics.catalog import try_handle_catalog_question, try_handle_fun_rank_question
from app.metrics.detect import extract_title_from_question
from app.metrics.mbti_commands import try_handle_mbti_command
from app.metrics.memory import FableSessionMemory
from app.metrics.title_card import is_title_only_question
from app.metrics.verbatim import try_handle_verbatim_body

ORIGIN = "원문본문입니다."
MODERN = "상황 봐가며 태세전환하는 한마디."
TITLES = ["늑대와 어린양", "박쥐와 족제비", "아버지와 아들들"]


def _fetch(title: str, content_type: str) -> dict[str, Any] | None:
    if title not in TITLES:
        return None
    if content_type == "origin":
        return {"text": ORIGIN, "citations": [{"source_file": "a.pdf", "page": 1, "snippet": ""}]}
    if content_type == "modern":
        return {"text": MODERN, "citations": [{"source_file": "a.pdf", "page": 2, "snippet": ""}]}
    return None


def _fake_llm(**kwargs: Any) -> str:
    return f"FAKE-{kwargs['mbti']}"


def test_한마디_with_mbti_uses_유형별_llm() -> None:
    """MBTI 설정 후 한마디 결론 → 유형별 재해석(문서 복붙 아님)."""
    memory = FableSessionMemory()
    memory.set_mbti("s1", "ENFP")
    result = try_handle_verbatim_body(
        "박쥐와 족제비 한마디 결론은",
        session_id="s1",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
        reinterpret_fn=_fake_llm,
    )
    assert result is not None
    assert result["answer"] == "FAKE-ENFP"
    assert result["answer"] != MODERN


def test_재해석_with_mbti_still_uses_llm() -> None:
    memory = FableSessionMemory()
    memory.set_mbti("s1", "INFP")
    result = try_handle_verbatim_body(
        "박쥐와 족제비 재해석",
        session_id="s1",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
        reinterpret_fn=_fake_llm,
    )
    assert result is not None
    assert result["answer"] == "FAKE-INFP"


def test_그대로_읽어줘_returns_origin() -> None:
    memory = FableSessionMemory()
    result = try_handle_verbatim_body(
        "아버지와 아들들 그대로 읽어줘",
        session_id="s1",
        memory=memory,
        known_titles=TITLES,
        fetch_fn=_fetch,
    )
    assert result is not None
    assert result["answer"] == ORIGIN


def test_우화목록_lists_titles() -> None:
    result = try_handle_catalog_question(
        "우화목록은",
        list_titles_fn=lambda: ["늑대와 어린양", "박쥐와 족제비"],
    )
    assert result is not None
    assert "늑대와 어린양" in result["answer"]
    assert "박쥐와 족제비" in result["answer"]


def test_전체_목록_with_space_lists_titles() -> None:
    """띄어쓴 「전체 목록」도 공백 제거 후 catalog 매칭."""
    result = try_handle_catalog_question(
        "전체 목록",
        list_titles_fn=lambda: ["늑대와 어린양", "박쥐와 족제비"],
    )
    assert result is not None
    assert "등록된 우화 목록" in result["answer"]
    assert "1. 늑대와 어린양" in result["answer"]


def test_목록_alone_lists_titles() -> None:
    """단독 「목록」도 제목 전량 나열."""
    result = try_handle_catalog_question(
        "목록",
        list_titles_fn=lambda: ["아버지와 아들들"],
    )
    assert result is not None
    assert "아버지와 아들들" in result["answer"]


def test_키워드_목록_is_not_catalog() -> None:
    """「키워드 목록」은 제목 카탈로그가 아님 (지표 경로용)."""
    result = try_handle_catalog_question(
        "키워드 목록",
        list_titles_fn=lambda: ["늑대와 어린양"],
    )
    assert result is None


def test_제일_재밌는_uses_fun_rank() -> None:
    metas = [
        {"title": "늑대와 어린양", "fun": 2},
        {"title": "박쥐와 족제비", "fun": 5},
        {"title": "아버지와 아들들", "fun": 4},
    ]
    result = try_handle_fun_rank_question(
        "제일 재밌는 우화가 뭐야",
        list_metas_fn=lambda: metas,
    )
    assert result is not None
    assert "박쥐와 족제비" in result["answer"]
    assert "토끼와 거북이" not in result["answer"]


def test_mbti_수정_shows_help() -> None:
    memory = FableSessionMemory()
    result = try_handle_mbti_command("mbti 수정", session_id="s1", memory=memory)
    assert result is not None
    assert "입력 예시" in result["answer"] or "수정 예시" in result["answer"]


def test_mbti로_바꿔_보려면_shows_help() -> None:
    memory = FableSessionMemory()
    result = try_handle_mbti_command(
        "mbti로 바꿔 보려면",
        session_id="s1",
        memory=memory,
    )
    assert result is not None
    assert "MBTI" in result["answer"] or "mbti" in result["answer"].lower()


def test_title_partial_last_char_missing() -> None:
    title = extract_title_from_question("아버지와 아들", TITLES)
    assert title == "아버지와 아들들"


def test_title_soft_suffix_얘기하고_is_title_only() -> None:
    assert is_title_only_question("늑대와 어린양 얘기하고", TITLES) == "늑대와 어린양"


def test_final_answer_blocks_empty_citations_after_search() -> None:
    state = {
        "question": "왜 박쥐가 배신자로 보이나?",
        "answer": "아이스크림을 먹습니다.",
        "citations": [],
        "observations": [],
        "tool_call_count": 2,
        "need_search": False,
        "search_query": "",
    }
    out = final_answer_node(state)
    assert "아이스크림" not in out["answer"]
    assert "찾지 못했" in out["answer"] or "알려주" in out["answer"]
