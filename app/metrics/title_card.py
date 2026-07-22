"""제목만 입력 → 우화 카드 전체(원문+한마디 결론+평가+키워드). LLM 없음."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.metrics.detect import extract_title_from_question
from app.metrics.format import format_metric_answer
from app.metrics.memory import FableSessionMemory

LookupFn = Callable[[str], dict[str, Any] | None]
FetchBodyFn = Callable[[str, str], dict[str, Any] | None]

# 제목만 볼 때 허용하는 조사·문장부호 (그 외 단어 있으면 제목만이 아님)
_TITLE_ONLY_TRAILING = re.compile(
    r"^[\s?!.。,\"'“”‘’의은는이가을를과와에만]*$"
)

# 「늑대와 어린양 얘기하고」처럼 제목+부드러운 요청 → 풀카드
_SOFT_SUFFIXES = (
    "얘기하고",
    "얘기해줘",
    "얘기해",
    "이야기해줘",
    "이야기해",
    "이야기",
    "말해줘",
    "말해",
    "알려줘",
    "알려",
)


def _strip_soft_suffix(rest: str) -> str:
    text = (rest or "").strip()
    for suffix in sorted(_SOFT_SUFFIXES, key=len, reverse=True):
        if text == suffix or text.endswith(suffix):
            text = text[: -len(suffix)].strip() if text.endswith(suffix) else ""
            break
    return text


def is_title_only_question(question: str, known_titles: list[str]) -> str | None:
    """질문이 알려진 제목(+조사·부드러운 요청)뿐이면 제목, 아니면 None."""
    cleaned = (question or "").strip()
    if not cleaned:
        return None
    title = extract_title_from_question(cleaned, known_titles)
    if not title:
        return None
    # 제목 제거 후 남는 게 조사·공백·소프트 요청뿐인지
    rest = cleaned.replace(title, "", 1)
    rest = _strip_soft_suffix(rest)
    if not _TITLE_ONLY_TRAILING.match(rest):
        return None
    return title


def format_full_fable_card(
    *,
    meta: dict[str, Any],
    origin_text: str,
    modern_text: str,
) -> str:
    """문서 기반 전체 카드 문자열."""
    title = str(meta.get("title") or "이 우화")
    parts: list[str] = [f"「{title}」"]

    origin = (origin_text or "").strip()
    if origin:
        parts.append("[내용]")
        parts.append(origin)

    modern = (modern_text or "").strip()
    if modern:
        parts.append("")
        parts.append("[한마디 결론]")
        parts.append(modern)

    parts.append("")
    parts.append(format_metric_answer(meta, "content_eval"))
    parts.append(format_metric_answer(meta, "keywords"))
    if meta.get("final_grade") is not None:
        parts.append(format_metric_answer(meta, "final_grade"))

    return "\n".join(parts).strip()


def try_handle_title_only_full_card(
    question: str,
    *,
    session_id: str | None,
    memory: FableSessionMemory,
    known_titles: list[str],
    lookup_fn: LookupFn,
    fetch_fn: FetchBodyFn,
) -> dict[str, Any] | None:
    """제목만이면 {answer, citations, mbti?}, 아니면 None."""
    title = is_title_only_question(question, known_titles)
    if not title:
        return None

    memory.set_title(session_id, title)
    meta = lookup_fn(title) or {"title": title}
    origin = fetch_fn(title, "origin") or {}
    modern = fetch_fn(title, "modern") or {}

    origin_text = str(origin.get("text") or "").strip()
    modern_text = str(modern.get("text") or "").strip()
    if not origin_text and not modern_text and not meta.get("fun"):
        return {
            "answer": f"「{title}」에 대한 카드 정보를 찾지 못했습니다.",
            "citations": [],
            "mbti": memory.get_mbti(session_id),
        }

    citations: list[Any] = []
    for blob in (origin, modern):
        for item in blob.get("citations") or []:
            if isinstance(item, dict):
                citations.append(item)

    return {
        "answer": format_full_fable_card(
            meta=meta,
            origin_text=origin_text,
            modern_text=modern_text,
        ),
        "citations": citations,
        "mbti": memory.get_mbti(session_id),
    }
