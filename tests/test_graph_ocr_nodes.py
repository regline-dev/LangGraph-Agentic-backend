"""OCR StateGraph 노드 단위 테스트 — 0-1 라우터 · 0-2 Tool #1 · 0-3 Tool #2 · 0-4 Tool #3.

기준: Docs/20260827_OCR_그래프_이관_gap분석.md 4절 매핑표.
"""

from app.graph.ocr.nodes import llm_router_node, tool_1_node, tool_2_node, tool_3_node
from app.graph.ocr.workflow import (
    _route_after_llm_router,
    _route_after_tool_1,
    _route_entry,
    build_ocr_graph,
)
from app.tools.ocr_receipt import (
    ADD_CONFIRM_TEMPLATE,
    AMOUNT_ONLY_GUIDE,
    ASK_WHICH_ITEM,
    CHITCHAT_GUIDE,
    EDIT_UNSUPPORTED_GUIDE,
    FieldConflict,
    LineItem,
    name_confirm_ask_message,
    name_confirm_cancel_message,
)


def test_tool1_merge_accepts_from_one_side() -> None:
    """3-4a: 기존 줄엔 단가가 없고 새 원문에 있으면 채택돼 확정된다."""
    state = {
        "lines": [LineItem(name="카트리지", qty=2)],
        "user_message": "카트리지 2개 단가 5000원",
    }
    result = tool_1_node(state)
    assert result["pending_kind"] is None
    assert len(result["lines"]) == 1
    assert result["lines"][0].unit_price == 5000
    assert result["lines"][0].amount_calc == 10000


def test_tool1_merge_both_missing_stays_unresolved() -> None:
    """3-4b: 양쪽 다 단가가 없으면 되묻지 않고 None으로 남아 다음 Tool(#2)이 판단한다."""
    state = {
        "lines": [LineItem(name="카트리지", qty=2)],
        "user_message": "카트리지 2개",
    }
    result = tool_1_node(state)
    assert result["pending_kind"] is None
    assert len(result["lines"]) == 1
    assert result["lines"][0].unit_price is None


def test_tool1_merge_conflict_asks_which_value() -> None:
    """3-4c: 같은 품목의 단가가 다르게 들어오면 되묻고 pending_kind=field_conflict."""
    state = {
        "lines": [LineItem(name="카트리지", qty=1, unit_price=1000)],
        "user_message": "카트리지 1개 단가 2000원",
    }
    result = tool_1_node(state)
    assert result["pending_kind"] == "field_conflict"
    assert "다르게 읽혔어요" in result["reply"]
    assert result["lines"][0].unit_price is None


def test_tool1_unmatched_line_queues_unclear() -> None:
    """정규식이 확정 못 한 줄은 버리지 않고 되묻는다 (3-4와 별개 큐)."""
    state = {"lines": [], "user_message": "미확인품목 999"}
    result = tool_1_node(state)
    assert result["pending_kind"] == "unclear"
    assert len(result["pending_unclear"]) == 1
    assert result["reply"] == result["pending_unclear"][0].ask_message


def test_tool1_resume_unclear_completes_with_followup_answer() -> None:
    """4-4b: 되물음 생성 → 답변 → 재진입 시 확정 목록에 반영된다."""
    asked = tool_1_node({"lines": [], "user_message": "미확인품목 999"})
    assert asked["pending_kind"] == "unclear"

    resumed = tool_1_node(
        {
            "lines": asked["lines"],
            "pending_unclear": asked["pending_unclear"],
            "pending_kind": "unclear",
            "user_message": "10개 500원",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["pending_unclear"] == []
    assert len(resumed["lines"]) == 1
    assert resumed["lines"][0].name == "미확인품목"
    assert resumed["lines"][0].qty == 10
    assert resumed["lines"][0].unit_price == 500


def test_tool1_resume_field_conflict_applies_choice() -> None:
    """4-4b: 값 충돌 되물음 → 선택 답변 → 재진입 시 확정 반영."""
    asked = tool_1_node(
        {
            "lines": [LineItem(name="카트리지", qty=1, unit_price=1000)],
            "user_message": "카트리지 1개 단가 2000원",
        }
    )
    assert asked["pending_kind"] == "field_conflict"
    conflict = asked["pending_field_conflict"]
    assert conflict.options == [1000, 2000]

    resumed = tool_1_node(
        {
            "lines": asked["lines"],
            "pending_field_conflict": conflict,
            "pending_kind": "field_conflict",
            "user_message": "2000원으로 할게요",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["pending_field_conflict"] is None
    assert resumed["lines"][0].unit_price == 2000


def test_tool1_resume_name_confirm_creates_item() -> None:
    """4-4b: 수량·단가 답변 → 재진입 시 새 품목으로 확정된다(예/아니 단계 없음)."""
    resumed = tool_1_node(
        {
            "lines": [],
            "pending_name_confirm": "커피",
            "pending_kind": "name_confirm",
            "user_message": "2개 3000원",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["pending_name_confirm"] is None
    assert len(resumed["lines"]) == 1
    assert resumed["lines"][0].name == "커피"
    assert resumed["lines"][0].qty == 2
    assert resumed["lines"][0].unit_price == 3000


def test_tool1_resume_name_confirm_bare_qty_and_price() -> None:
    """단위 없는 '2 3000원'도 수량 2·단가 3000으로 확정한다."""
    resumed = tool_1_node(
        {
            "lines": [],
            "pending_name_confirm": "율무차",
            "pending_kind": "name_confirm",
            "user_message": "2 3000원",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["lines"][0].name == "율무차"
    assert resumed["lines"][0].qty == 2
    assert resumed["lines"][0].unit_price == 3000


def test_tool1_resume_name_confirm_deny_keeps_existing_lines() -> None:
    """부정은 후보만 취소하고 기존 확정 목록은 유지한다."""
    existing = [
        LineItem(name="A4용지", qty=1, unit_price=1000),
        LineItem(name="아메리카노", qty=2, unit_price=2000),
    ]
    resumed = tool_1_node(
        {
            "lines": existing,
            "pending_name_confirm": "율무차",
            "pending_kind": "name_confirm",
            "preview_opened": True,
            "user_message": "아니요",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["pending_name_confirm"] is None
    assert [item.name for item in resumed["lines"]] == ["A4용지", "아메리카노"]
    assert resumed["reply"] == name_confirm_cancel_message("율무차")
    assert resumed["candidate_discarded"] is True


def test_tool1_resume_name_confirm_qty_unit_merges_after_preview() -> None:
    """미리보기 이후 수량·단가 답은 추가 확인 없이 확정 목록에 합치고 단위를 유지한다."""
    resumed = tool_1_node(
        {
            "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
            "pending_name_confirm": "율무차",
            "pending_kind": "name_confirm",
            "preview_opened": True,
            "user_message": "2잔 4000원",
        }
    )
    assert resumed["pending_kind"] is None
    by_name = {item.name: item for item in resumed["lines"]}
    assert "커피" in by_name
    assert by_name["율무차"].qty == 2
    assert by_name["율무차"].qty_unit == "잔"
    assert by_name["율무차"].unit_price == 4000
    assert resumed["candidate_lines"] == []


def test_tool2_all_confirmed_returns_true() -> None:
    """0-3: 품목이 전부 채워져 있으면 전체 확정으로 판정하고 되물음이 없다."""
    state = {"lines": [LineItem(name="물", qty=3, unit_price=1000)]}
    result = tool_2_node(state)
    assert result["all_confirmed"] is True
    assert result["pending_kind"] is None
    assert result["followup_question"] == ""
    assert result["total"] == 3000


def test_tool2_missing_price_asks_and_sets_fill_name() -> None:
    """0-3: 단가가 비어 있으면 fill_name 되물음을 만든다 (check_completeness 그대로)."""
    state = {"lines": [LineItem(name="커피", qty=2, unit_price=None)]}
    result = tool_2_node(state)
    assert result["all_confirmed"] is False
    assert result["pending_kind"] == "fill_name"
    assert "커피" in result["followup_question"]
    assert "단가" in result["followup_question"]
    assert result["reply"] == result["followup_question"]


def test_tool2_missing_qty_asks_fill_name() -> None:
    """수량만 비면 fill_name + 수량 전용 문구. 단가 문구를 쓰지 않는다."""
    from app.tools.ocr_receipt import ASK_MISSING_QTY

    state = {"lines": [LineItem(name="율무차", qty=None, unit_price=3000)]}
    result = tool_2_node(state)
    assert result["all_confirmed"] is False
    assert result["pending_kind"] == "fill_name"
    assert result["reply"] == ASK_MISSING_QTY.format(name="율무차")
    assert "단가" not in result["reply"]


def test_tool2_resume_fill_name_qty_then_price_completes() -> None:
    """수량 결측 재개에 수량·단가를 같이 주면 스테일 단가까지 덮어쓰고 확정된다."""
    asked = tool_2_node({"lines": [LineItem(name="율무차", qty=None, unit_price=3000)]})
    assert asked["pending_kind"] == "fill_name"

    resumed = tool_2_node(
        {
            "lines": asked["lines"],
            "pending_kind": "fill_name",
            "user_message": "2개 2000원",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["all_confirmed"] is True
    assert resumed["lines"][0].qty == 2
    assert resumed["lines"][0].unit_price == 2000
    assert resumed["total"] == 4000


def test_tool2_resume_fill_name_completes_after_answer() -> None:
    """4-4b: fill_name 되물음 → 답변 → 재진입 시 apply_fill로 반영된다."""
    asked = tool_2_node({"lines": [LineItem(name="커피", qty=2, unit_price=None)]})
    assert asked["pending_kind"] == "fill_name"

    resumed = tool_2_node(
        {
            "lines": asked["lines"],
            "pending_kind": "fill_name",
            "user_message": "3000원",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["all_confirmed"] is True
    assert resumed["lines"][0].unit_price == 3000
    assert resumed["total"] == 6000


def test_tool2_resume_conflict_accepts_calculated_amount() -> None:
    """4-4b: 금액 검산 되물음("계산값으로 할까요?") → 동의 → accept_calculated_amounts 반영."""
    item = LineItem(name="커피", qty=2, unit_price=3000, amount_ocr=5000)
    asked = tool_2_node({"lines": [item]})
    assert asked["pending_kind"] == "conflict"
    assert asked["lines"][0].amount_conflict is True

    resumed = tool_2_node(
        {
            "lines": asked["lines"],
            "pending_kind": "conflict",
            "user_message": "네",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["all_confirmed"] is True
    assert resumed["lines"][0].amount_conflict is False
    assert resumed["lines"][0].amount_ocr == 6000


def test_tool3_unsupported_edit_still_guides() -> None:
    """회귀: 단가 변경·삭제 등 미지원 요청은 그대로 안내만 하고 끝난다."""
    state = {
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
        "user_message": "커피 단가 삭제해줘",
    }
    result = tool_3_node(state)
    assert result["reply"] == EDIT_UNSUPPORTED_GUIDE
    assert result["pending_kind"] is None
    assert "lines" not in result


def test_tool3_quantity_edit_success_revalidates() -> None:
    """0-4: 수량 수정 반영 후 check_completeness로 재검증까지 통과한다."""
    state = {
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
        "user_message": "커피 수량 5개로 바꿔줘",
    }
    result = tool_3_node(state)
    assert result["lines"][0].qty == 5
    assert result["pending_kind"] is None
    assert result["all_confirmed"] is True
    assert result["total"] == 15000
    assert "커피" in result["reply"]


def test_tool3_ambiguous_item_asks_then_resumes() -> None:
    """4-4b: 품목을 특정 못하면 ask_item으로 되묻고, 다음 턴 품목명 답변으로 재개한다."""
    state = {
        "lines": [
            LineItem(name="커피", qty=2, unit_price=3000),
            LineItem(name="주스", qty=1, unit_price=2000),
        ],
        "user_message": "5개로 바꿔줘",
    }
    asked = tool_3_node(state)
    assert asked["pending_kind"] == "ask_item"
    assert asked["pending_qty"] == 5

    resumed = tool_3_node(
        {
            "lines": asked["lines"],
            "pending_kind": "ask_item",
            "pending_qty": asked["pending_qty"],
            "user_message": "커피",
        }
    )
    assert resumed["pending_kind"] is None
    assert resumed["all_confirmed"] is True
    assert resumed["lines"][0].qty == 5


def test_llm_router_greeting_is_chitchat_and_ends() -> None:
    """0-1: 인사만이면 chitchat으로 분류하고 안내만 반환한다(pending_kind 없음)."""
    result = llm_router_node({"user_message": "안녕하세요"})
    assert result["intent"] == "chitchat"
    assert "pending_kind" not in result
    assert result["reply"] == CHITCHAT_GUIDE


def test_llm_router_single_word_chitchat_asks_name_confirm() -> None:
    """0-1: 단어 하나짜리 chitchat은 품목명 후보로 보고 되묻는다(4-4b name_confirm)."""
    result = llm_router_node({"user_message": "커피", "lines": []})
    assert result["intent"] == "chitchat"
    assert result["pending_kind"] == "name_confirm"
    assert result["pending_name_confirm"] == "커피"
    assert result["reply"] == name_confirm_ask_message("커피")


def test_llm_router_multiword_chitchat_after_preview_goes_unclear() -> None:
    """6-2a: 미리보기 이후(has_lines=True) "품목명+동사"류는 인사가 아니므로
    unclear 되물음 흐름으로 넘어간다(name_confirm이 아님, 단어 2개 이상이라서).
    """
    state = {
        "user_message": "율무차 추가",
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
    }
    result = llm_router_node(state)
    assert result["intent"] == "chitchat"
    assert result["pending_kind"] == "unclear"
    assert len(result["pending_unclear"]) == 1
    assert result["pending_unclear"][0].raw == "율무차 추가"
    assert result["reply"] == result["pending_unclear"][0].ask_message
    assert _route_after_llm_router({**state, **result}) == "end"


def test_llm_router_multiword_chitchat_first_turn_goes_unclear() -> None:
    """0-1: 첫 턴(has_lines=False, 아직 lines 없음)에도 동일 규칙이 적용돼야 한다."""
    state = {"user_message": "우유 추가", "lines": []}
    result = llm_router_node(state)
    assert result["intent"] == "chitchat"
    assert result["pending_kind"] == "unclear"
    assert len(result["pending_unclear"]) == 1
    assert result["pending_unclear"][0].raw == "우유 추가"


def test_llm_router_greeting_after_preview_still_asks_item_fields() -> None:
    """6-2a: 미리보기 이후에도 순수 인사는 여전히 안내만 하고 끝난다(회귀 방지)."""
    state = {
        "user_message": "안녕하세요",
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
    }
    result = llm_router_node(state)
    assert result["intent"] == "chitchat"
    assert "pending_kind" not in result
    assert result["reply"] == CHITCHAT_GUIDE


def test_llm_router_meaningless_chitchat_sentence_goes_unclear() -> None:
    """의미 없는 잡담 문장도 인사가 아니면 unclear 되물음으로 간다."""
    state = {"user_message": "오늘 날씨가 좋네요", "lines": []}
    result = llm_router_node(state)
    assert result["intent"] == "chitchat"
    assert result["pending_kind"] == "unclear"
    assert len(result["pending_unclear"]) == 1


def test_llm_router_unclear_roundtrip_resolves_via_tool1() -> None:
    """라우터가 만든 unclear 되물음을 tool_1_node가 기존 _resume_unclear로 그대로 처리한다."""
    router_result = llm_router_node({"user_message": "율무차 추가", "lines": []})
    assert router_result["pending_kind"] == "unclear"

    resume_state = {
        "lines": [],
        "pending_kind": "unclear",
        "pending_unclear": router_result["pending_unclear"],
        "user_message": "3개 500원이야",
    }
    resumed = tool_1_node(resume_state)
    assert resumed["pending_kind"] is None
    assert len(resumed["lines"]) == 1
    assert resumed["lines"][0].name == "율무차"
    assert resumed["lines"][0].qty == 3
    assert resumed["lines"][0].unit_price == 500


def test_llm_router_data_intent_routes_to_tool1() -> None:
    """0-1: 품목·수량·단가가 파싱되면 data로 분류해 tool_1로 라우팅된다."""
    state = {"user_message": "커피 2개 3000원", "lines": []}
    result = llm_router_node(state)
    assert result["intent"] == "data"
    assert _route_after_llm_router({**state, **result}) == "tool_1"


def test_llm_router_edit_intent_routes_to_tool3() -> None:
    """0-1: 기존 품목에 수정 키워드가 있으면 edit으로 분류해 tool_3로 라우팅된다."""
    state = {
        "user_message": "커피 3개로 바꿔줘",
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
    }
    result = llm_router_node(state)
    assert result["intent"] == "edit"
    assert _route_after_llm_router({**state, **result}) == "tool_3"


def test_llm_router_amount_only_ends_turn() -> None:
    """0-1: 금액만 언급하면 amount_only로 분류해 안내만 하고 턴을 끝낸다."""
    state = {
        "user_message": "금액이 얼마예요",
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
    }
    result = llm_router_node(state)
    assert result["intent"] == "amount_only"
    assert result["reply"] == AMOUNT_ONLY_GUIDE
    assert _route_after_llm_router({**state, **result}) == "end"


def test_tool1_stages_candidate_when_preview_opened() -> None:
    """미리보기 이후 완결된 새 품목은 추가 확인 없이 확정 목록에 바로 합친다."""
    state = {
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
        "preview_opened": True,
        "user_message": "우유 2개 1500원",
    }
    result = tool_1_node(state)
    names = {item.name for item in result["lines"]}
    assert names == {"커피", "우유"}
    assert result["candidate_lines"] == []
    assert result["pending_kind"] is None


def test_tool1_add_confirm_yes_merges_into_lines() -> None:
    """6-5/6-6: "추가할까요?"에 긍정 → 후보가 확정 목록에 합쳐진다."""
    state = {
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
        "candidate_lines": [LineItem(name="우유", qty=2, unit_price=1500)],
        "pending_kind": "add_confirm",
        "preview_opened": True,
        "user_message": "네",
    }
    result = tool_1_node(state)
    assert result["pending_kind"] is None
    assert result["candidate_lines"] == []
    assert result["candidate_discarded"] is False
    names = {item.name for item in result["lines"]}
    assert names == {"커피", "우유"}


def test_tool1_add_confirm_no_discards_candidate() -> None:
    """6-5a: "추가할까요?"에 부정 → 후보만 폐기, 확정 목록·미리보기는 유지."""
    state = {
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
        "candidate_lines": [LineItem(name="우유", qty=2, unit_price=1500)],
        "pending_kind": "add_confirm",
        "preview_opened": True,
        "user_message": "아니요",
    }
    result = tool_1_node(state)
    assert result["pending_kind"] is None
    assert result["candidate_lines"] == []
    assert result["candidate_discarded"] is True
    assert len(result["lines"]) == 1
    assert result["lines"][0].name == "커피"


def test_tool1_candidate_unclear_resolves_into_candidate_not_lines() -> None:
    """6-3/4-4b: 후보가 미확정(unclear)이면 lines가 아니라 candidate_lines로 해소된다."""
    asked = tool_1_node(
        {
            "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
            "preview_opened": True,
            "user_message": "미확인품목 999",
        }
    )
    assert asked["pending_kind"] == "unclear"
    assert asked["candidate_lines"] == []
    assert len(asked["lines"]) == 1  # 기존 확정 목록은 안 건드림

    resumed = tool_1_node(
        {
            "lines": asked["lines"],
            "candidate_lines": asked["candidate_lines"],
            "pending_unclear": asked["pending_unclear"],
            "pending_kind": "unclear",
            "preview_opened": True,
            "user_message": "10개 500원",
        }
    )
    assert resumed["pending_kind"] is None
    assert len(resumed["lines"]) == 2
    names = {item.name for item in resumed["lines"]}
    assert names == {"커피", "미확인품목"}
    assert resumed["candidate_lines"] == []


def test_tool2_full_confirmation_does_not_touch_preview_opened() -> None:
    """3-1/3-2: preview_opened는 이제 action=="preview"(어댑터)가 세팅한다 —
    tool_2_node는 전체 확정 시에도 이 값을 스스로 세팅하지 않는다(입력값 유지)."""
    result = tool_2_node({"lines": [LineItem(name="커피", qty=2, unit_price=3000)]})
    assert result["all_confirmed"] is True
    assert "preview_opened" not in result


def test_route_after_tool1_ends_turn_when_pending_kind_set() -> None:
    """버그 수정: tool_1이 되물음(pending_kind)을 낸 채로 끝나면 tool_2로 안 넘어간다."""
    assert _route_after_tool_1({"pending_kind": "unclear"}) == "end"
    assert _route_after_tool_1({"pending_kind": "add_confirm"}) == "end"
    assert _route_after_tool_1({"pending_kind": None}) == "tool_2"


def test_full_graph_add_flow_after_preview() -> None:
    """미리보기 이후 완결 품목은 한 턴에 확정 목록으로 합쳐진다."""
    graph = build_ocr_graph()
    base_state = {
        "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
        "preview_opened": True,
    }

    confirmed = graph.invoke({**base_state, "user_message": "우유 2개 1500원"})
    assert confirmed["pending_kind"] is None
    assert confirmed["all_confirmed"] is True
    names = {item.name for item in confirmed["lines"]}
    assert names == {"커피", "우유"}
    assert confirmed["total"] == 2 * 3000 + 2 * 1500


def test_route_entry_conflict_unrelated_goes_interrupt() -> None:
    """무관한 메시지는 conflict tool로 직행하지 않고 인터럽트 확정 노드로 간다."""
    state = {
        "pending_kind": "conflict",
        "lines": [LineItem(name="A4용지", qty=2, unit_price=30000, amount_ocr=50000)],
        "user_message": "율무차 추가",
    }
    assert _route_entry(state) == "pending_interrupt"


def test_route_entry_conflict_yes_still_goes_tool2() -> None:
    """유효한 긍정 답은 기존처럼 tool_2로 재개한다."""
    state = {
        "pending_kind": "conflict",
        "lines": [LineItem(name="A4용지", qty=2, unit_price=30000, amount_ocr=50000)],
        "user_message": "네",
    }
    assert _route_entry(state) == "tool_2"


def test_graph_conflict_unrelated_confirms_calc_and_handles_new_message() -> None:
    """conflict 중 '율무차 추가' → 계산값 확정 + 새 메시지는 라우터(unclear)로."""
    graph = build_ocr_graph()
    item = LineItem(name="A4용지", qty=2, unit_price=30000, amount_ocr=50000)
    item.recompute()
    result = graph.invoke(
        {
            "lines": [item],
            "pending_kind": "conflict",
            "user_message": "율무차 추가",
        }
    )
    assert result["lines"][0].amount_conflict is False
    assert result["lines"][0].amount_ocr == 60000
    assert result["pending_kind"] == "unclear"
    assert "확정했습니다" in (result.get("interrupt_notice") or "")
    assert "확정했습니다" not in result["reply"]
    assert "율무차" in result["reply"]


def test_graph_field_conflict_unrelated_confirms_existing_and_handles_new_message() -> None:
    """field_conflict 중 무관 메시지 → 기존 확정값(options[0]) 유지 + 새 메시지 처리."""
    graph = build_ocr_graph()
    conflict = FieldConflict(name="카트리지", field="unit_price", options=[1000, 2000])
    result = graph.invoke(
        {
            "lines": [LineItem(name="카트리지", qty=1, unit_price=None)],
            "pending_kind": "field_conflict",
            "pending_field_conflict": conflict,
            "user_message": "율무차 추가",
        }
    )
    assert result["lines"][0].unit_price == 1000
    assert result["pending_field_conflict"] is None
    assert result["pending_kind"] == "unclear"
    assert "확정했습니다" in (result.get("interrupt_notice") or "")
    assert "확정했습니다" not in result["reply"]
    assert "율무차" in result["reply"]


def test_graph_fill_name_unrelated_keeps_original_ask() -> None:
    graph = build_ocr_graph()
    result = graph.invoke(
        {
            "lines": [LineItem(name="커피", qty=2)],
            "pending_kind": "fill_name",
            "user_message": "율무차 추가",
        }
    )
    assert result["pending_kind"] == "fill_name"
    assert result["lines"][0].unit_price is None
    assert "단가" in result["reply"]


def test_graph_missing_qty_then_qty_price_confirms() -> None:
    """재현: 수량만 빈 율무차에 '2개 2000원' → 채워지고 확정."""
    graph = build_ocr_graph()
    result = graph.invoke(
        {
            "lines": [LineItem(name="율무차", qty=None, unit_price=3000)],
            "pending_kind": "fill_name",
            "user_message": "2개 2000원",
        }
    )
    assert result["pending_kind"] is None
    assert result["all_confirmed"] is True
    assert result["lines"][0].qty == 2
    assert result["lines"][0].unit_price == 2000


def test_graph_name_confirm_bare_qty_price_confirms() -> None:
    """율무차 확인 뒤 '2 3000원'이면 한 턴에 수량·단가가 채워진다."""
    graph = build_ocr_graph()
    result = graph.invoke(
        {
            "lines": [],
            "pending_kind": "name_confirm",
            "pending_name_confirm": "율무차",
            "user_message": "2 3000원",
        }
    )
    assert result["pending_kind"] is None
    assert result["all_confirmed"] is True
    assert result["lines"][0].name == "율무차"
    assert result["lines"][0].qty == 2
    assert result["lines"][0].unit_price == 3000


def test_graph_unclear_unrelated_keeps_original_ask() -> None:
    graph = build_ocr_graph()
    asked = tool_1_node({"lines": [], "user_message": "미확인품목 999"})
    original_ask = asked["reply"]
    result = graph.invoke(
        {
            "lines": asked["lines"],
            "pending_kind": "unclear",
            "pending_unclear": asked["pending_unclear"],
            "user_message": "율무차 추가",
        }
    )
    assert result["pending_kind"] == "unclear"
    assert result["pending_unclear"] == asked["pending_unclear"]
    assert result["reply"] == original_ask


def test_graph_name_confirm_unrelated_keeps_original_ask() -> None:
    graph = build_ocr_graph()
    result = graph.invoke(
        {
            "lines": [],
            "pending_kind": "name_confirm",
            "pending_name_confirm": "커피",
            "user_message": "율무차 추가",
        }
    )
    assert result["pending_kind"] == "name_confirm"
    assert result["pending_name_confirm"] == "커피"
    assert result["reply"] == name_confirm_ask_message("커피")
    assert result.get("lines") in (None, [])


def test_graph_ask_item_unrelated_keeps_original_ask() -> None:
    graph = build_ocr_graph()
    result = graph.invoke(
        {
            "lines": [
                LineItem(name="커피", qty=2, unit_price=3000),
                LineItem(name="주스", qty=1, unit_price=2000),
            ],
            "pending_kind": "ask_item",
            "pending_qty": 5,
            "user_message": "율무차 추가",
        }
    )
    assert result["pending_kind"] == "ask_item"
    assert result["pending_qty"] == 5
    assert result["reply"] == ASK_WHICH_ITEM
    assert result["lines"][0].qty == 2


def test_graph_add_confirm_unrelated_keeps_original_ask() -> None:
    graph = build_ocr_graph()
    milk = LineItem(name="우유", qty=2, unit_price=1500)
    result = graph.invoke(
        {
            "lines": [LineItem(name="커피", qty=2, unit_price=3000)],
            "candidate_lines": [milk],
            "pending_kind": "add_confirm",
            "preview_opened": True,
            "user_message": "율무차 추가",
        }
    )
    assert result["pending_kind"] == "add_confirm"
    assert len(result["candidate_lines"]) == 1
    assert result["candidate_lines"][0].name == "우유"
    assert result["reply"] == ADD_CONFIRM_TEMPLATE.format(n=1)
    assert not result.get("candidate_discarded")
