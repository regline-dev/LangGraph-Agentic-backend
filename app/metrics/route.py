"""지표 질문이면 metadata 답/되묻기, 아니면 None(기존 그래프)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.metrics.detect import detect_metric_kind, extract_title_from_question
from app.metrics.format import clarify_which_fable, format_metric_answer
from app.metrics.memory import FableSessionMemory

LookupFn = Callable[[str], dict[str, Any] | None]


def try_handle_metric_question(
    question: str,
    *,
    session_id: str | None,
    memory: FableSessionMemory,
    known_titles: list[str],
    lookup_fn: LookupFn,
) -> dict[str, Any] | None:
    """지표·키워드 질문 처리.

    Returns:
        {answer, citations: []} 또는 지표가 아니면 None
    """
    cleaned = (question or "").strip()
    if not cleaned:
        return None

    # 제목이 질문에 있으면 단기 메모리에 기록 (지표 여부와 무관)
    mentioned = extract_title_from_question(cleaned, known_titles)
    if mentioned:
        memory.set(session_id, mentioned)

    kind = detect_metric_kind(cleaned)
    if kind is None:
        return None

    title = mentioned or memory.get(session_id)
    if not title:
        return {"answer": clarify_which_fable(kind), "citations": []}

    meta = lookup_fn(title)
    if not meta:
        return {
            "answer": f"「{title}」에 대한 정보를 찾지 못했습니다.",
            "citations": [],
        }

    memory.set(session_id, str(meta.get("title") or title))
    return {
        "answer": format_metric_answer(meta, kind),
        "citations": [],
    }
