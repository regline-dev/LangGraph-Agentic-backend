"""LangGraph Agent State — PDF 검색 Tool 루프용."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """그래프가 주고받는 상태.

    - need_search: LLM(또는 주입된 판단 함수)이 검색이 필요하다고 봤는지
    - tool_call_count: search_documents 호출 횟수 (0/1/2… 검증용)
    - observations: Tool 결과 원문 목록
    - citations: API 응답용 근거
    """

    question: str
    need_search: bool
    search_query: str
    tool_call_count: int
    observations: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    answer: str
