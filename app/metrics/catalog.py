"""우화 목록 · 재미도 순위 — 문서(메타) 기반, LLM 금지."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ListTitlesFn = Callable[[], list[str]]
ListMetasFn = Callable[[], list[dict[str, Any]]]

# 공백 제거 후 비교. 「목록」단독은 exact만 — 「키워드목록」오탐 방지
_CATALOG_EXACT = frozenset({"목록", "전체목록", "우화목록"})
_CATALOG_CONTAINS = (
    "우화목록",
    "전체목록",
    "목록은",
    "목록알려",
    "어떤우화가있어",
)

_FUN_RANK_MARKERS = (
    "제일 재밌",
    "제일 재미",
    "가장 재밌",
    "가장 재미",
    "재밌는 우화",
    "재미있는 우화",
    "재미도 높은",
)


def _compact_for_catalog_match(text: str) -> str:
    """목록 의도 판별용 — 공백만 제거 (제목 매칭에는 쓰지 않음)."""
    return "".join((text or "").split())


def _is_catalog_intent(compact: str) -> bool:
    core = compact.rstrip("?!.…")
    if core in _CATALOG_EXACT:
        return True
    return any(marker in compact for marker in _CATALOG_CONTAINS)


def try_handle_catalog_question(
    question: str,
    *,
    list_titles_fn: ListTitlesFn,
) -> dict[str, Any] | None:
    """목록 질문이면 제목 나열, 아니면 None."""
    cleaned = (question or "").strip()
    if not cleaned:
        return None
    # 「전체 목록」「우화 목록은」등 띄어쓰기 변형 흡수
    compact = _compact_for_catalog_match(cleaned)
    if not _is_catalog_intent(compact):
        return None

    titles = [t.strip() for t in list_titles_fn() if t and str(t).strip()]
    if not titles:
        return {
            "answer": "등록된 우화 목록을 찾지 못했습니다.",
            "citations": [],
        }

    lines = ["등록된 우화 목록입니다."]
    for index, title in enumerate(titles, start=1):
        lines.append(f"{index}. {title}")
    return {"answer": "\n".join(lines), "citations": []}


def try_handle_fun_rank_question(
    question: str,
    *,
    list_metas_fn: ListMetasFn,
    top_n: int = 3,
) -> dict[str, Any] | None:
    """재미도 순위 질문이면 메타 fun 기준 Top-N, 아니면 None."""
    cleaned = (question or "").strip()
    if not cleaned:
        return None
    if not any(marker in cleaned for marker in _FUN_RANK_MARKERS):
        return None

    metas = list(list_metas_fn() or [])
    scored: list[tuple[str, int]] = []
    for meta in metas:
        title = str(meta.get("title") or "").strip()
        if not title:
            continue
        try:
            fun = int(meta.get("fun"))
        except (TypeError, ValueError):
            continue
        scored.append((title, fun))

    if not scored:
        return {
            "answer": "재미도 정보가 있는 우화를 찾지 못했습니다.",
            "citations": [],
        }

    scored.sort(key=lambda item: (-item[1], item[0]))
    top = scored[: max(1, top_n)]
    lines = ["문서(재미도) 기준 순위입니다."]
    for index, (title, fun) in enumerate(top, start=1):
        lines.append(f"{index}. 「{title}」 재미도 {fun}/5")
    return {"answer": "\n".join(lines), "citations": []}
