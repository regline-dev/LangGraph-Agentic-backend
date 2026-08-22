"""PDF 문서 없음 / 히트 시 LLM 가공 정책."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from app.config import get_settings


GeneralLlmFn = Callable[[str], str]

_NO_DOCUMENT_ANSWER = "학습 데이터가 없습니다."


def load_llm_polish_enabled() -> bool:
    """어드민 공통 설정 — 문서 히트 시 LLM 가공 ON/OFF. 조회 실패 시 기본 ON."""
    settings = get_settings()
    url = f"{settings.admin_api_base_url.rstrip('/')}/api/system/pdf-answer-policy"
    request = Request(url, headers={"X-Admin-User-Id": "pdf-agent"})
    try:
        with urlopen(request, timeout=settings.admin_api_timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        if "llm_polish_enabled" in data:
            return bool(data.get("llm_polish_enabled"))
        # 구 API 필드 호환
        return bool(data.get("llm_fallback_enabled", True))
    except Exception as exc:  # noqa: BLE001
        print(
            "[PDF 답변 정책 조회]\n"
            f"  api=GET {url}\n"
            "  result=fail\n"
            f"  reason={exc}\n"
            "  fallback=polish_enabled",
            flush=True,
        )
        return True


# 하위 호환 별칭 (테스트·구 import)
def load_llm_fallback_enabled() -> bool:
    return load_llm_polish_enabled()


def format_citation_snippets(citations: list[dict[str, Any]]) -> str:
    """LLM 가공 OFF일 때 검색 발췌만 보여 준다."""
    lines: list[str] = ["관련 문서 발췌:"]
    for index, citation in enumerate(citations, start=1):
        source = str(citation.get("source_file") or "unknown")
        page = citation.get("page", "")
        snippet = str(citation.get("snippet") or "").strip()
        if not snippet:
            continue
        lines.append(f"{index}. ({source} p.{page}) {snippet}")
    if len(lines) == 1:
        return _NO_DOCUMENT_ANSWER
    return "\n".join(lines)


def build_no_document_response(
    question: str = "",
    *,
    fallback_enabled: bool | None = None,
    llm_invoke: GeneralLlmFn | None = None,
) -> dict[str, Any]:
    """문서를 못 찾으면 항상 동일 — LLM을 호출하지 않는다 (거짓 정보 방지)."""
    _ = question, fallback_enabled, llm_invoke
    return {"answer": _NO_DOCUMENT_ANSWER, "citations": []}


def apply_hit_answer_policy(
    *,
    answer: str,
    citations: list[dict[str, Any]] | None,
    polish_enabled: bool,
) -> dict[str, Any]:
    """문서 히트 시 ON=LLM 정리 답, OFF=발췌만."""
    cites = list(citations or [])
    if polish_enabled:
        text = (answer or "").strip()
        if not text and cites:
            text = format_citation_snippets(cites)
        return {"answer": text or _NO_DOCUMENT_ANSWER, "citations": cites}
    if cites:
        return {"answer": format_citation_snippets(cites), "citations": cites}
    text = (answer or "").strip()
    return {"answer": text or _NO_DOCUMENT_ANSWER, "citations": []}
