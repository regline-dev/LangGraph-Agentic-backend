"""StateGraph 구성 — LLM 판단 → (필요 시 Tool) → 최종 답변."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    MAX_TOOL_CALLS,
    DecideFn,
    SearchFn,
    final_answer_node,
    make_llm_decision_node,
    make_tool_node,
)
from app.graph.state import AgentState

# 외부(테스트)에서 상한 상수 import 가능
__all__ = ["MAX_TOOL_CALLS", "build_agent_graph", "build_groq_agent_graph", "run_agent"]


def _route_after_decision(state: AgentState) -> Literal["tool", "final"]:
    """검색이 필요하고 상한 미만이면 tool, 아니면 final."""
    if state.get("need_search") and int(state.get("tool_call_count") or 0) < MAX_TOOL_CALLS:
        return "tool"
    return "final"


def build_agent_graph(*, decide_fn: DecideFn, search_fn: SearchFn):
    """Agentic 검색 그래프를 컴파일한다.

    Args:
        decide_fn: 검색 필요 여부 판단 (운영: Groq, 테스트: Fake)
        search_fn: search_documents에 해당하는 검색 실행
    """
    graph = StateGraph(AgentState)
    graph.add_node("llm_decision", make_llm_decision_node(decide_fn))
    graph.add_node("tool", make_tool_node(search_fn))
    graph.add_node("final_answer", final_answer_node)

    graph.add_edge(START, "llm_decision")
    graph.add_conditional_edges(
        "llm_decision",
        _route_after_decision,
        {"tool": "tool", "final": "final_answer"},
    )
    # Tool 후 재판단 (0회 시나리오에서는 이 경로에 안 들어옴)
    graph.add_edge("tool", "llm_decision")
    graph.add_edge("final_answer", END)

    return graph.compile()


def build_groq_agent_graph(*, search_fn: SearchFn):
    """운영용: Groq 판단 + 주입된 검색 함수로 그래프를 만든다."""
    from app.graph.groq_decision import make_groq_decide_fn_from_settings

    return build_agent_graph(decide_fn=make_groq_decide_fn_from_settings(), search_fn=search_fn)


def run_agent(graph: Any, *, question: str) -> AgentState:
    """질문을 그래프에 넣고 최종 state를 반환한다."""
    cleaned = (question or "").strip()
    if not cleaned:
        raise ValueError("question이 비어 있습니다.")

    initial: AgentState = {
        "question": cleaned,
        "need_search": False,
        "search_query": "",
        "tool_call_count": 0,
        "observations": [],
        "citations": [],
        "answer": "",
    }
    return graph.invoke(initial)
