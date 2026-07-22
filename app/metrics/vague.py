"""짧은·애매 질문 → 되묻기 (벡터 검색·요약 단정 금지)."""

from __future__ import annotations

import re
from typing import Any

from app.metrics.detect import detect_metric_kind, extract_title_from_question

# 이 길이(공백·문장부호 제외) 이하면 제목 없을 때 애매로 본다. 「늑대」=2
_MAX_VAGUE_COMPACT_LEN = 4

# 단독 입력 → 의도 되묻기 (Groq·검색으로 흘리지 않음)
_STANDALONE_INTENT_WORDS = frozenset({"해석", "결론", "mbti"})

_STANDALONE_CLARIFY_ANSWER = (
    "어떤 걸 알고 싶으신가요?\n"
    "예: 내용 / 줄거리 / 한마디 결론 / 내용평가 / 유형별 해석"
)

_CHITCHAT_MARKERS = (
    "누구",
    "안녕",
    "헬로",
    "hello",
    "자기소개",
    "너는",
    "너 누구",
)


def try_clarify_vague_question(
    question: str,
    *,
    known_titles: list[str],
) -> dict[str, Any] | None:
    """애매하면 {answer, citations: []}, 아니면 None(다음 단계로)."""
    cleaned = (question or "").strip()
    if not cleaned:
        return None

    # 단독 의도어는 제목 유무와 무관하게 되묻기 (예: 「해석」만)
    if _is_standalone_intent(cleaned):
        return {
            "answer": _STANDALONE_CLARIFY_ANSWER,
            "citations": [],
        }

    # 지표·키워드는 metric 라우터가 처리 (내용평가 포함)
    if detect_metric_kind(cleaned) is not None:
        return None

    # 우화 제목이 질문에 있으면 검색/그래프 허용
    # (내용·줄거리는 verbatim이 본문 그대로 처리)
    if extract_title_from_question(cleaned, known_titles):
        return None

    # 인사·자기소개는 Tool 0 경로
    if _is_chitchat(cleaned):
        return None

    if not _is_too_vague(cleaned):
        return None

    return {
        "answer": _format_vague_title_clarify(cleaned, known_titles),
        "citations": [],
    }


def _compact_query(question: str) -> str:
    return re.sub(r"[\s?!.。,\"'“”‘’]+", "", question or "")


def _titles_containing(fragment: str, known_titles: list[str]) -> list[str]:
    """질문에 쓴 글자가 제목에 포함된 우화 목록 (known_titles 순서 유지)."""
    needle = (fragment or "").strip()
    if not needle:
        return []
    hits: list[str] = []
    seen: set[str] = set()
    for title in known_titles:
        cleaned = (title or "").strip()
        if not cleaned or cleaned in seen:
            continue
        if needle in cleaned:
            hits.append(cleaned)
            seen.add(cleaned)
    return hits


def _format_vague_title_clarify(question: str, known_titles: list[str]) -> str:
    """되묻기 + (있으면) 「글자」가 들어간 제목 번호 목록."""
    compact = _compact_query(question)
    candidates = _titles_containing(compact, known_titles)
    if not candidates:
        return (
            "어떤 우화를 말씀하시나요?\n"
            "제목이나 알고 싶은 내용(내용평가, 키워드, 줄거리 등)을 알려주세요."
        )

    lines = [
        "어떤 우화를 말씀하시나요?",
        f"「{compact}」가 들어간 제목:",
    ]
    for index, title in enumerate(candidates, start=1):
        lines.append(f"{index}. {title}")
    return "\n".join(lines)


def _is_standalone_intent(question: str) -> bool:
    """공백·문장부호만 제거한 뒤 해석/결론/mbti 단독인지."""
    compact = _compact_query(question).lower()
    return compact in _STANDALONE_INTENT_WORDS


def _is_chitchat(question: str) -> bool:
    lowered = question.lower()
    return any(marker in lowered for marker in _CHITCHAT_MARKERS)


def _is_too_vague(question: str) -> bool:
    """제목·지표 없이 너무 짧으면 애매."""
    return len(_compact_query(question)) <= _MAX_VAGUE_COMPACT_LEN
