"""OCR StateGraph 구성 — PDF workflow.py와 별도 그래프.

LLM(라우터) → Tool #1 / #2 / #3.
`/ocr/turn`은 턴 단위 요청이므로, 되물음·추가확인 대기는 그래프 안에서 붙잡지 않고
END로 턴을 끝낸 뒤 다음 턴의 START 진입 분기(`_route_entry`)에서 이어받는다.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.graph.ocr.nodes import (
    _AUTO_CONFIRM_KINDS,
    _ocr_debug,
    _trace_route,
    is_valid_pending_answer,
    llm_router_node,
    pending_hold_node,
    pending_interrupt_node,
    tool_1_node,
    tool_2_node,
    tool_3_node,
)
from app.graph.ocr.state import OcrState
from app.tools.ocr_receipt import PendingKind

__all__ = ["build_ocr_graph"]

_EntryRoute = Literal[
    "llm_router",
    "tool_1",
    "tool_2",
    "tool_3",
    "pending_interrupt",
    "pending_hold",
]

# 4-4: 되물음 답변이 어느 Tool로 들어가야 하는지. 되물음을 만든 Tool이 곧 답을
# 처리할 Tool이다. 새 되물음이 생기면 여기에만 줄을 더한다.
_PENDING_KIND_ROUTE: dict[PendingKind, _EntryRoute] = {
    "conflict": "tool_2",  # 금액 검산 되물음 → accept_calculated_amounts
    "fill_name": "tool_2",  # 필수값 채우기 → apply_fill
    "unclear": "tool_1",  # 미매칭 줄 해석 → 재파싱·병합
    "field_conflict": "tool_1",  # 병합 충돌 선택 → apply_field_conflict_choice
    "name_confirm": "tool_1",  # "품목입니까?" → 품목 생성·병합
    "ask_item": "tool_3",  # "어떤 품목?" → apply_natural_edit 재시도
    "add_confirm": "tool_1",  # 6-5 "추가할까요?" (예=합침 / 아니오=폐기)
}


def _route_entry(state: OcrState) -> _EntryRoute:
    """START 진입 분기 — 대기 중인 응답이면 LLM 라우터를 건너뛴다.

    유효한 답이면 해당 Tool로 직행(4-4). 유효하지 않으면:
    - conflict/field_conflict: 기본값 확정 후 같은 메시지를 라우터로 (pending_interrupt)
    - 나머지: 새 메시지는 무시하고 원래 되물음 유지 (pending_hold)
    """
    pending_kind = state.get("pending_kind")
    user_message = (state.get("user_message") or "").strip()
    _ocr_debug("_route_entry", step="enter", pending_kind=pending_kind, user_message=user_message)
    if not pending_kind:
        dest: _EntryRoute = "llm_router"
        _ocr_debug("_route_entry", step="branch", reason="no_pending", dest=dest)
    elif is_valid_pending_answer(state):
        dest = _PENDING_KIND_ROUTE[pending_kind]
        _ocr_debug(
            "_route_entry",
            step="branch",
            reason="valid_answer",
            group="resume_tool",
            dest=dest,
        )
    elif pending_kind in _AUTO_CONFIRM_KINDS:
        dest = "pending_interrupt"
        _ocr_debug(
            "_route_entry",
            step="branch",
            reason="unrelated",
            group="auto_confirm",
            dest=dest,
        )
    else:
        dest = "pending_hold"
        _ocr_debug(
            "_route_entry",
            step="branch",
            reason="unrelated",
            group="hold",
            dest=dest,
        )
    _trace_route("entry", dest, state)
    return dest


def _route_after_llm_router(
    state: OcrState,
) -> Literal["tool_1", "tool_2", "tool_3", "end"]:
    """0-1 의도 분류 결과로 다음 Tool을 고른다."""
    intent = state.get("intent")
    _ocr_debug("_route_after_llm_router", step="enter", intent=intent)
    if intent in ("chitchat", "amount_only"):
        # 6-2 인사·금액만 언급 → 안내만 하고 턴 종료.
        # 6-2b 복귀는 다음 채팅 입력이 새 턴으로 들어오는 것.
        dest: Literal["tool_1", "tool_2", "tool_3", "end"] = "end"
    elif intent == "edit":
        dest = "tool_3"  # 6-2a 수정 → 7-0 Tool #3 진입
    elif intent == "fill":
        dest = "tool_2"
    else:
        # data(신규 품목 언급) — 6-2a 추가 → 6-3 구조화부터
        dest = "tool_1"
    _ocr_debug("_route_after_llm_router", step="branch", intent=intent, dest=dest)
    _trace_route("after_llm_router", dest, state)
    return dest


def _route_after_tool_1(state: OcrState) -> Literal["tool_2", "end"]:
    """6-5a: 후보를 버린 경우엔 검산 없이 턴을 끝낸다(확정 목록·미리보기는 유지).

    tool_1이 되물음(unclear/field_conflict/add_confirm 등 pending_kind)을 낸
    채로 끝났으면 역시 검산 없이 턴을 끝낸다 — 그대로 tool_2로 보내면
    check_completeness가 아직 미해결인 pending_kind를 덮어써 되물음이
    사라지는 버그가 있었다(재현 확인 후 수정, 6-5 작업 중 발견).
    """
    _ocr_debug(
        "_route_after_tool_1",
        step="enter",
        pending_kind=state.get("pending_kind"),
        candidate_discarded=bool(state.get("candidate_discarded")),
    )
    if state.get("candidate_discarded") or state.get("pending_kind"):
        dest: Literal["tool_2", "end"] = "end"
        _ocr_debug(
            "_route_after_tool_1",
            step="branch",
            reason="pending_or_discarded",
            dest=dest,
        )
    else:
        dest = "tool_2"
        _ocr_debug("_route_after_tool_1", step="branch", reason="complete", dest=dest)
    _trace_route("after_tool_1", dest, state)
    return dest


def build_ocr_graph():
    """OCR 전용 그래프를 컴파일한다."""
    graph = StateGraph(OcrState)
    graph.add_node("llm_router", llm_router_node)
    graph.add_node("tool_1", tool_1_node)
    graph.add_node("tool_2", tool_2_node)
    graph.add_node("tool_3", tool_3_node)
    graph.add_node("pending_interrupt", pending_interrupt_node)
    graph.add_node("pending_hold", pending_hold_node)

    graph.add_conditional_edges(
        START,
        _route_entry,
        {
            "llm_router": "llm_router",
            "tool_1": "tool_1",
            "tool_2": "tool_2",
            "tool_3": "tool_3",
            "pending_interrupt": "pending_interrupt",
            "pending_hold": "pending_hold",
        },
    )
    graph.add_conditional_edges(
        "llm_router",
        _route_after_llm_router,
        {"tool_1": "tool_1", "tool_2": "tool_2", "tool_3": "tool_3", "end": END},
    )
    graph.add_conditional_edges(
        "tool_1",
        _route_after_tool_1,
        {"tool_2": "tool_2", "end": END},
    )
    # 7-2: 수정 반영 후 #2 재검사. 상단 "(자동) 영수증 기본선택"은 다시 타지 않으며,
    # 미리보기 직접 갱신 여부는 state의 preview_ready로 구분한다.
    graph.add_edge("tool_3", "tool_2")
    # 4-1·4-2: 미확정이 남으면 되물음만 내보내고 턴 종료. 다음 턴은 _route_entry가 tool_2로 직행.
    graph.add_edge("tool_2", END)
    graph.add_edge("pending_interrupt", "llm_router")
    graph.add_edge("pending_hold", END)

    return graph.compile()
