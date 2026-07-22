"""LangGraph 노드 — 판단 / Tool 실행 / 최종 답변.

판단은 decide_fn 주입. 운영 기본은 Groq(`app.graph.groq_decision`).
테스트는 Fake decide_fn으로 API 없이 검증한다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.graph.state import AgentState

# Tool 재시도 상한 — 무한 루프 방지 (Tool 0/1/2 학습 범위 안)
MAX_TOOL_CALLS = 3

# 판단 함수: state → {need_search, search_query?, answer?}
DecideFn = Callable[[AgentState], dict[str, Any]]
# 검색 함수: query → search_documents와 같은 결과 리스트
SearchFn = Callable[[str], list[dict[str, Any]]]


def make_llm_decision_node(decide_fn: DecideFn):
    """LLM 판단 노드 팩토리 — 검색 필요 여부와 (불필요 시) 답변을 채운다."""

    def llm_decision_node(state: AgentState) -> dict[str, Any]:
        # 상한에 도달하면 더 이상 검색하지 않고 답변으로 마무리
        if int(state.get("tool_call_count") or 0) >= MAX_TOOL_CALLS:
            answer = (state.get("answer") or "").strip()
            if not answer:
                answer = "검색을 여러 번 시도했지만 충분한 답을 만들지 못했습니다."
            return {
                "need_search": False,
                "search_query": "",
                "answer": answer,
            }

        decision = decide_fn(state)
        updates: dict[str, Any] = {
            "need_search": bool(decision.get("need_search", False)),
            "search_query": str(decision.get("search_query", "") or ""),
        }
        # 검색 불필요일 때만 최종 답변을 이 단계에서 채울 수 있다
        if "answer" in decision and decision["answer"]:
            updates["answer"] = str(decision["answer"])
        return updates

    return llm_decision_node


def make_tool_node(search_fn: SearchFn):
    """search_documents Tool 노드 — 검색만 수행하고 Observation을 state에 반영."""

    def tool_node(state: AgentState) -> dict[str, Any]:
        query = (state.get("search_query") or state.get("question") or "").strip()
        if not query:
            raise ValueError("검색 쿼리가 비어 있습니다.")

        hits = search_fn(query)
        count = int(state.get("tool_call_count") or 0) + 1
        observations = list(state.get("observations") or [])
        observations.extend(hits)

        new_citations = [
            {
                "source_file": hit.get("metadata", {}).get("source_file", ""),
                "page": hit.get("metadata", {}).get("page", 0),
                "snippet": str(hit.get("page_content", ""))[:200],
                "score": float(hit.get("score") or 0.0),
            }
            for hit in hits
        ]
        citations = list(state.get("citations") or [])
        citations.extend(new_citations)

        return {
            "tool_call_count": count,
            "observations": observations,
            "citations": citations,
            # 재판단을 위해 일단 검색 플래그를 끈다 (다음 판단이 다시 켤 수 있음)
            "need_search": False,
        }

    return tool_node


_NO_DOC_ANSWER = (
    "문서에서 관련 내용을 찾지 못했습니다. "
    "우화 제목과 함께 내용·줄거리·한마디 결론·내용평가 등으로 물어봐 주세요."
)


def final_answer_node(state: AgentState) -> dict[str, Any]:
    """최종 답변 노드 — 이미 answer가 있으면 유지, 없으면 안내 문구.

    검색을 돌렸는데 근거(citations)가 없으면 환각 답을 막는다.
    """
    answer = (state.get("answer") or "").strip()
    citations = list(state.get("citations") or [])
    tool_count = int(state.get("tool_call_count") or 0)
    observations = list(state.get("observations") or [])

    if tool_count > 0 and not citations and not observations:
        answer = _NO_DOC_ANSWER
    elif not answer:
        answer = "답변을 생성하지 못했습니다."

    return {
        "answer": answer,
        "citations": citations,
        "tool_call_count": tool_count,
    }
