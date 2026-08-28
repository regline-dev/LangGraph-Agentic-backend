"""OCR StateGraph 노드 — 시그니처만. 본문은 후속 지시 때 구현.

기준: Docs/20260827_ocr_flow_diagram_llm_tool_수정본_2차.html 「Tool Node 구조」
각 노드는 PDF 그래프와 같은 규약으로 state 갱신분(dict)만 반환한다.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.graph.ocr.state import OcrState
from app.tools.ocr_receipt import (
    ADD_CONFIRM_TEMPLATE,
    AMOUNT_ONLY_GUIDE,
    ASK_ITEM_FIELDS,
    ASK_QTY_PRICE_AMOUNT,
    ASK_WHICH_ITEM,
    CHITCHAT_GUIDE,
    EDIT_UNSUPPORTED_GUIDE,
    KIND_READY,
    READ_OK_PREFIX,
    LineItem,
    UnclearLine,
    accept_calculated_amounts,
    apply_field_conflict_choice,
    apply_fill,
    apply_natural_edit,
    check_completeness,
    classify_intent,
    extract_price_from_text,
    extract_qty_from_text,
    extract_qty_general,
    extract_qty_unit,
    field_conflict_message,
    guess_item_name,
    is_affirmative,
    is_greeting,
    is_negative,
    is_unsupported_edit,
    merge_line_lists,
    name_confirm_ask_message,
    name_confirm_cancel_message,
    parse_lines_from_text,
    parse_raw_with_unclear,
    resolve_unclear_answer,
    suggest_item,
    totals,
    unclear_ask_message,
)

# tool_2_node가 전체 확정 시 내는 기본 안내(turn.py의 after_lines_changed, 132행과 동일 문구).
# kind_id는 이 그래프가 다루지 않는 값이라 "아직 선택 전"을 기본값으로 삼는다 — 이미 kind_id가
# 있는 세션이면 어댑터(app/graph/ocr/service.py)가 이 문구를 감지해 다음 문구로 바꿔치기한다
# (turn.py 134행과 동일 문구): f"{READ_OK_PREFIX}\n미리보기를 눌러 주세요."
KIND_NOT_SELECTED_REPLY = f"{READ_OK_PREFIX}\n{KIND_READY}"

# 계산 가능한 기본값이 있어, 무관 요청이면 그 값으로 확정한 뒤 라우터로 넘긴다.
_AUTO_CONFIRM_KINDS = frozenset({"conflict", "field_conflict"})

_DEBUG_VALUE_MAX = 180


def _debug_on() -> bool:
    return get_settings().debug_onoff


def _short_debug_value(value: Any) -> str:
    if value is None:
        return "-"
    text = value if isinstance(value, str) else repr(value)
    text = text.replace("\n", " | ")
    if len(text) > _DEBUG_VALUE_MAX:
        return text[:_DEBUG_VALUE_MAX] + "..."
    return text


def _ocr_debug(fn: str, **fields: Any) -> None:
    """흐름 추적 print. DEBUG_ONOFF=1일 때만. 이벤트 로그(api/ocr.py)와 별개."""
    if not _debug_on():
        return
    lines = [f"[{datetime.now(timezone.utc).isoformat()}] debug={fn}"]
    for key, value in fields.items():
        lines.append(f"  {key}={_short_debug_value(value)}")
    print("\n".join(lines), flush=True)


def _pending_target_lines(state: OcrState) -> list[LineItem]:
    """재개 대상 목록. preview 이후 후보가 있으면 candidate_lines."""
    if state.get("preview_opened") and state.get("candidate_lines"):
        return list(state.get("candidate_lines") or [])
    return list(state.get("lines") or [])


def is_valid_pending_answer(state: OcrState) -> bool:
    """대기 중인 되물음에 대한 유효한 답인지. 판정만 하고 state는 바꾸지 않는다."""
    kind = state.get("pending_kind")
    answer = (state.get("user_message") or "").strip()
    _ocr_debug("is_valid_pending_answer", step="enter", pending_kind=kind, user_message=answer)
    if not kind or not answer:
        _ocr_debug("is_valid_pending_answer", step="return", valid=False, reason="empty_kind_or_answer")
        return False

    if kind == "conflict":
        valid = is_affirmative(answer)
        _ocr_debug("is_affirmative", text=answer, result=valid)
        _ocr_debug("is_valid_pending_answer", step="return", valid=valid, reason="conflict_affirmative")
        return valid

    if kind == "field_conflict":
        conflict = state.get("pending_field_conflict")
        if conflict is None:
            _ocr_debug("is_valid_pending_answer", step="return", valid=False, reason="no_field_conflict")
            return False
        probe = deepcopy(_pending_target_lines(state))
        _ocr_debug(
            "apply_field_conflict_choice",
            step="probe",
            text=answer,
            name=getattr(conflict, "name", None),
            options=getattr(conflict, "options", None),
        )
        valid = apply_field_conflict_choice(answer, probe, conflict)
        _ocr_debug("is_valid_pending_answer", step="return", valid=valid, reason="field_conflict_choice")
        return valid

    if kind == "fill_name":
        target = deepcopy(_pending_target_lines(state))
        pending_name = check_completeness(target).pending_name
        _ocr_debug("check_completeness", step="fill_name_probe", pending_name=pending_name)
        if not pending_name:
            _ocr_debug("is_valid_pending_answer", step="return", valid=False, reason="no_fill_name")
            return False
        before = [(item.qty, item.unit_price) for item in target]
        apply_fill(answer, target, pending_name)
        after = [(item.qty, item.unit_price) for item in target]
        valid = before != after
        _ocr_debug("apply_fill", step="probe", text=answer, pending_name=pending_name, changed=valid)
        _ocr_debug("is_valid_pending_answer", step="return", valid=valid, reason="fill_name_changed")
        return valid

    if kind == "unclear":
        queue = list(state.get("pending_unclear") or [])
        if not queue:
            _ocr_debug("is_valid_pending_answer", step="return", valid=False, reason="empty_unclear_queue")
            return False
        current = queue[0]
        if is_affirmative(answer) and current.suggestion is not None:
            _ocr_debug("is_valid_pending_answer", step="return", valid=True, reason="unclear_affirmative")
            return True
        parsed = parse_lines_from_text(answer)
        _ocr_debug("parse_lines_from_text", text=answer, parsed_count=len(parsed))
        if any(item.unit_price is not None for item in parsed):
            _ocr_debug("is_valid_pending_answer", step="return", valid=True, reason="unclear_full_parse")
            return True
        valid = extract_qty_general(answer) is not None or extract_price_from_text(answer) is not None
        _ocr_debug(
            "is_valid_pending_answer",
            step="return",
            valid=valid,
            reason="unclear_qty_or_price",
        )
        return valid

    if kind == "name_confirm":
        if is_negative(answer):
            _ocr_debug("is_negative", text=answer, result=True)
            _ocr_debug("is_valid_pending_answer", step="return", valid=True, reason="name_confirm_deny")
            return True
        qty = extract_qty_general(answer)
        price = extract_price_from_text(answer)
        valid = qty is not None or price is not None
        _ocr_debug(
            "is_valid_pending_answer",
            step="return",
            valid=valid,
            reason="name_confirm_qty_or_price",
            qty=qty,
            price=price,
        )
        return valid

    if kind == "ask_item":
        name = guess_item_name(answer)
        _ocr_debug("guess_item_name", text=answer, name=name)
        if not name:
            _ocr_debug("is_valid_pending_answer", step="return", valid=False, reason="ask_item_no_name")
            return False
        valid = any(item.name == name for item in (state.get("lines") or []))
        _ocr_debug("is_valid_pending_answer", step="return", valid=valid, reason="ask_item_name_match")
        return valid

    if kind == "add_confirm":
        yes = is_affirmative(answer)
        no = is_negative(answer)
        _ocr_debug("is_affirmative", text=answer, result=yes)
        _ocr_debug("is_negative", text=answer, result=no)
        _ocr_debug("is_valid_pending_answer", step="return", valid=yes or no, reason="add_confirm_yes_or_no")
        return yes or no

    _ocr_debug("is_valid_pending_answer", step="return", valid=False, reason="unknown_kind")
    return False


def _hold_reply(state: OcrState) -> str:
    """그룹2: 기존 되물음 문구를 상태에서 다시 만든다. 새 질문을 만들지 않는다."""
    kind = state.get("pending_kind")
    if kind == "fill_name":
        return check_completeness(_pending_target_lines(state)).message or ASK_QTY_PRICE_AMOUNT
    if kind == "unclear":
        queue = list(state.get("pending_unclear") or [])
        if queue:
            return queue[0].ask_message
        return ASK_ITEM_FIELDS
    if kind == "name_confirm":
        name = state.get("pending_name_confirm") or ""
        return name_confirm_ask_message(name) if name else ASK_ITEM_FIELDS
    if kind == "ask_item":
        return ASK_WHICH_ITEM
    if kind == "add_confirm":
        n = len(state.get("candidate_lines") or [])
        return ADD_CONFIRM_TEMPLATE.format(n=n)
    return ASK_ITEM_FIELDS


def pending_hold_node(state: OcrState) -> dict[str, Any]:
    """그룹2 무관 요청 — 새 메시지는 무시하고 원래 되물음만 유지."""
    reply = _hold_reply(state)
    _ocr_debug(
        "pending_hold_node",
        step="enter",
        group="hold",
        pending_kind=state.get("pending_kind"),
        user_message=(state.get("user_message") or "").strip(),
        reply=reply,
    )
    return _trace(
        "pending_hold_node",
        state,
        {
            "pending_kind": state.get("pending_kind"),
            "reply": reply,
        },
    )


def pending_interrupt_node(state: OcrState) -> dict[str, Any]:
    """그룹1 무관 요청 — 기본값 확정 안내 후 pending을 비워 라우터가 새 메시지를 받게 한다."""
    kind = state.get("pending_kind")
    in_candidate_mode = bool(state.get("preview_opened") and state.get("candidate_lines"))
    existing_lines = list(state.get("lines") or [])
    target = list(state.get("candidate_lines") or []) if in_candidate_mode else existing_lines
    _ocr_debug(
        "pending_interrupt_node",
        step="enter",
        group="auto_confirm",
        pending_kind=kind,
        user_message=(state.get("user_message") or "").strip(),
        in_candidate_mode=in_candidate_mode,
    )

    notice = "계산값으로 확정했습니다."
    updates: dict[str, Any] = {
        "pending_kind": None,
        "interrupt_notice": notice,
    }

    if kind == "conflict":
        conflicted = [item for item in target if item.amount_conflict]
        if conflicted:
            notice = "\n".join(
                (
                    f"{item.name} 수량 {item.qty}개, 개당 {item.unit_price:,}원, "
                    f"총 {item.amount_calc:,}원으로 확정했습니다."
                )
                for item in conflicted
                if item.qty is not None and item.unit_price is not None and item.amount_calc is not None
            )
        _ocr_debug(
            "accept_calculated_amounts",
            step="call",
            names=[item.name for item in conflicted],
        )
        accept_calculated_amounts(target)
        updates["interrupt_notice"] = notice or "계산값으로 확정했습니다."
        updates["pending_kind"] = None
        _ocr_debug(
            "pending_interrupt_node",
            step="chosen",
            pending_kind="conflict",
            chosen="amount_calc",
            notice=updates["interrupt_notice"],
        )
    elif kind == "field_conflict":
        conflict = state.get("pending_field_conflict")
        if conflict is not None and conflict.options:
            # 기존 확정값(options[0]). 신규([-1])는 검증 전이라 무응답 때 채택하지 않는다.
            chosen = conflict.options[0]
            _ocr_debug(
                "apply_field_conflict_choice",
                step="call",
                chosen=chosen,
                options=conflict.options,
                field=conflict.field,
                name=conflict.name,
            )
            apply_field_conflict_choice(str(chosen), target, conflict)
            if conflict.field == "unit_price":
                notice = f"{conflict.name} 단가를 {chosen:,}원으로 확정했습니다."
            else:
                notice = f"{conflict.name} 수량을 {chosen}개로 확정했습니다."
        updates["interrupt_notice"] = notice
        updates["pending_field_conflict"] = None
        _ocr_debug(
            "pending_interrupt_node",
            step="chosen",
            pending_kind="field_conflict",
            chosen=conflict.options[0] if conflict is not None and conflict.options else None,
            notice=notice,
        )

    if in_candidate_mode:
        updates["candidate_lines"] = target
        updates["lines"] = existing_lines
    else:
        updates["lines"] = target
    return _trace("pending_interrupt_node", state, updates)


def _with_interrupt_notice(state: OcrState, updates: dict[str, Any]) -> dict[str, Any]:
    """확정 안내는 reply에 붙이지 않는다. 어댑터가 prior_reply로 따로 내려 말풍선을 나눈다."""
    return updates


def _trace(node: str, state: OcrState, updates: dict[str, Any]) -> dict[str, Any]:
    """노드 종료 시점 print. DEBUG_ONOFF=1일 때만."""
    updates = _with_interrupt_notice(state, updates)
    _ocr_debug(
        node,
        step="return",
        user_message=(state.get("user_message") or state.get("raw_text") or "").strip(),
        pending_kind_in=state.get("pending_kind"),
        intent=updates.get("intent") or state.get("intent"),
        pending_kind_out=updates["pending_kind"] if "pending_kind" in updates else "-",
        reply=updates.get("reply"),
        interrupt_notice=updates.get("interrupt_notice") or state.get("interrupt_notice"),
        result="ok",
    )
    return updates


def _trace_route(where: str, dest: str, state: OcrState) -> None:
    """조건부 엣지 목적지 print. DEBUG_ONOFF=1일 때만."""
    _ocr_debug(
        f"ocr_route_{where}",
        step="route",
        dest=dest,
        intent=state.get("intent"),
        pending_kind=state.get("pending_kind"),
        user_message=(state.get("user_message") or "").strip(),
        result="ok",
    )


def llm_router_node(state: OcrState) -> dict[str, Any]:
    """0-1 LLM(라우터) — 의도 분류 후 다음 Tool 선택.

    `intent`(chitchat/data/edit/amount_only)를 채워 반환하면
    `_route_after_llm_router`가 그 값으로 분기한다. `fill`은 텍스트가 아니라
    직전 되물음 종류(pending_kind)로 정해지므로 여기서는 내지 않는다 —
    이 노드는 pending_kind가 None인 새 턴에서만 `_route_entry`를 통해 들어온다.

    이미지 업로드는 user_message가 비고 raw_text에 Vision 추출 텍스트가 담겨
    들어온다(_ingest_new_lines와 같은 폴백) — user_message가 있으면 그게 우선이다.
    """
    cleaned = (state.get("user_message") or state.get("raw_text") or "").strip()
    lines = list(state.get("lines") or [])
    _ocr_debug("llm_router_node", step="enter", user_message=cleaned, lines=len(lines))

    greeting = is_greeting(cleaned)
    _ocr_debug("is_greeting", text=cleaned, result=greeting)
    if greeting:
        _ocr_debug("llm_router_node", step="branch", reason="greeting", intent="chitchat")
        return _trace("llm_router_node", state, {"intent": "chitchat", "reply": CHITCHAT_GUIDE})

    _ocr_debug("classify_intent", step="call", text=cleaned, has_lines=bool(lines))
    intent = classify_intent(cleaned, has_lines=bool(lines))
    _ocr_debug("classify_intent", step="return", intent=intent)

    if intent == "amount_only":
        # 6-2: 금액만 언급 — 안내만 하고 턴 종료(_route_after_llm_router가 end로 보냄).
        _ocr_debug("llm_router_node", step="branch", reason="amount_only", intent=intent)
        return _trace("llm_router_node", state, {"intent": intent, "reply": AMOUNT_ONLY_GUIDE})

    if intent == "chitchat":
        if not cleaned:
            _ocr_debug("llm_router_node", step="branch", reason="empty_chitchat", intent=intent)
            return _trace("llm_router_node", state, {"intent": intent, "reply": ASK_ITEM_FIELDS})
        if len(cleaned.split()) == 1:
            # 단어 하나 → 품목명 후보로 보고 확인한다(turn.py와 동일 판단, 4-4b name_confirm 유지).
            # 다음 턴 답변은 pending_kind="name_confirm"으로 tool_1_node가 받는다.
            _ocr_debug("llm_router_node", step="branch", reason="single_word_name_confirm", name=cleaned)
            return _trace(
                "llm_router_node",
                state,
                {
                    "intent": intent,
                    "pending_kind": "name_confirm",
                    "pending_name_confirm": cleaned,
                    "reply": name_confirm_ask_message(cleaned),
                },
            )
        # 6-2/6-2a: 인사가 아니면 나머지는 전부 품목 후보로 본다 — 단어 2개 이상도
        # 기존 unclear 되물음 흐름(parse_raw_with_unclear가 만드는 것과 같은 UnclearLine)을
        # 그대로 재사용한다. 새 되물음 로직을 만들지 않기 위해 suggest_item/unclear_ask_message를 직접 쓴다.
        _ocr_debug("suggest_item", step="call", text=cleaned)
        suggestion = suggest_item(cleaned)
        ask_message = unclear_ask_message(cleaned, suggestion)
        _ocr_debug(
            "llm_router_node",
            step="branch",
            reason="chitchat_to_unclear",
            suggestion_name=getattr(suggestion, "name", None),
        )
        return _trace(
            "llm_router_node",
            state,
            {
                "intent": intent,
                "pending_kind": "unclear",
                "pending_unclear": [UnclearLine(raw=cleaned, suggestion=suggestion, ask_message=ask_message)],
                "reply": ask_message,
            },
        )

    # data → tool_1, edit → tool_3 (라우팅은 _route_after_llm_router가 처리).
    _ocr_debug("llm_router_node", step="branch", reason="route_by_intent", intent=intent)
    return _trace("llm_router_node", state, {"intent": intent})


def _finalize_candidates(candidates: list[LineItem], lines: list[LineItem]) -> dict[str, Any]:
    """6-4/6-5: 후보 완결 판정. 완결이면 바로 lines에 합친다(추가할까요? 생략).

    `check_completeness`를 그대로 재사용하되 대상이 `lines`가 아니라
    `candidate_lines`라는 점만 다르다.
    """
    updates: dict[str, Any] = {"lines": lines, "candidate_lines": candidates}
    _ocr_debug("_finalize_candidates", step="enter", candidates=len(candidates))
    if not candidates:
        updates["pending_kind"] = None
        _ocr_debug("_finalize_candidates", step="branch", reason="empty_candidates")
        return updates
    _ocr_debug("check_completeness", step="call", lines=len(candidates))
    result = check_completeness(candidates)
    if result.ok:
        merged, conflicts = merge_line_lists(lines, candidates)
        updates = {
            "lines": merged,
            "candidate_lines": [],
            "candidate_discarded": False,
            "pending_kind": None,
            "all_confirmed": True,
            "reply": KIND_NOT_SELECTED_REPLY,
        }
        if conflicts:
            updates["pending_kind"] = "field_conflict"
            updates["pending_field_conflict"] = conflicts[0]
            updates["reply"] = field_conflict_message(conflicts[0])
            _ocr_debug("_finalize_candidates", step="branch", reason="field_conflict_on_merge")
            return updates
        _ocr_debug("_finalize_candidates", step="branch", reason="auto_merge")
        return updates
    updates["pending_kind"] = result.pending_kind
    updates["reply"] = result.message or ""
    _ocr_debug(
        "_finalize_candidates",
        step="branch",
        reason="incomplete",
        pending_kind=result.pending_kind,
    )
    return updates


def _ingest_new_lines(state: OcrState) -> dict[str, Any]:
    """pending_kind가 없을 때 — 새 원문을 확정 목록에 합친다(6-3).

    `preview_opened`(6-3 이후, 미리보기가 이미 열린 상태)면 곧장 `lines`에
    합치지 않고 `candidate_lines`에 쌓아 6-5 확인을 받는다.
    """
    raw = (state.get("raw_text") or state.get("user_message") or "").strip()
    existing_lines = list(state.get("lines") or [])
    existing_unclear = list(state.get("pending_unclear") or [])
    _ocr_debug(
        "_ingest_new_lines",
        step="enter",
        raw=raw,
        existing_lines=len(existing_lines),
        preview_opened=bool(state.get("preview_opened")),
    )
    _ocr_debug("parse_raw_with_unclear", step="call", raw=raw)
    confirmed, new_unclear = parse_raw_with_unclear(raw)
    _ocr_debug(
        "parse_raw_with_unclear",
        step="return",
        confirmed=len(confirmed),
        unclear=len(new_unclear),
    )
    # 여기 큐는 3-4와 별개다 — parse_raw_with_unclear가 애초에 확정 패턴으로
    # 못 읽은 줄(품목·수량·단가 형식 자체가 불명확한 원문)을 쌓아 둔 것이다.
    pending_unclear = existing_unclear + new_unclear

    if state.get("preview_opened"):
        existing_candidates = list(state.get("candidate_lines") or [])
        _ocr_debug(
            "merge_line_lists",
            step="call",
            mode="preview_candidates",
            existing=len(existing_candidates),
            incoming=len(confirmed),
        )
        merged_candidates, conflicts = merge_line_lists(existing_candidates, confirmed)
        _ocr_debug("merge_line_lists", step="return", conflicts=len(conflicts))
        updates: dict[str, Any] = {
            "lines": existing_lines,
            "candidate_lines": merged_candidates,
            "pending_unclear": pending_unclear,
        }
        if conflicts:
            updates["pending_kind"] = "field_conflict"
            updates["pending_field_conflict"] = conflicts[0]
            updates["reply"] = field_conflict_message(conflicts[0])
            _ocr_debug("_ingest_new_lines", step="branch", reason="field_conflict_preview")
            return updates
        if pending_unclear:
            updates["pending_kind"] = "unclear"
            updates["reply"] = pending_unclear[0].ask_message
            _ocr_debug("_ingest_new_lines", step="branch", reason="unclear_preview")
            return updates
        _ocr_debug("_ingest_new_lines", step="branch", reason="finalize_candidates")
        return {**updates, **_finalize_candidates(merged_candidates, existing_lines)}

    # merge_line_lists가 3-4a/b/c를 그대로 처리한다.
    # 3-4a 한쪽만 채움→채택 · 3-4b 둘 다 비움→conflict 없이 None 유지(미확정)
    # · 3-4c 값이 다름→FieldConflict.
    _ocr_debug(
        "merge_line_lists",
        step="call",
        mode="confirmed_lines",
        existing=len(existing_lines),
        incoming=len(confirmed),
    )
    merged, conflicts = merge_line_lists(existing_lines, confirmed)
    _ocr_debug("merge_line_lists", step="return", conflicts=len(conflicts))
    updates = {"lines": merged, "pending_unclear": pending_unclear}

    if conflicts:
        # 3-4c: 병합 충돌 — 되물어야 하므로 미매칭 큐보다 먼저 처리한다.
        updates["pending_kind"] = "field_conflict"
        updates["pending_field_conflict"] = conflicts[0]
        updates["reply"] = field_conflict_message(conflicts[0])
        _ocr_debug("_ingest_new_lines", step="branch", reason="field_conflict")
        return updates

    if pending_unclear:
        # 정규식이 확정 못 한 줄 — 버리지 않고 되묻는다.
        updates["pending_kind"] = "unclear"
        updates["reply"] = pending_unclear[0].ask_message
        _ocr_debug("_ingest_new_lines", step="branch", reason="unclear")
        return updates

    updates["pending_kind"] = None
    updates["pending_field_conflict"] = None
    _ocr_debug("_ingest_new_lines", step="branch", reason="merged_ok")
    return updates


def _resume_unclear(state: OcrState) -> dict[str, Any]:
    """4-4b: pending_kind="unclear" 재진입 — 큐 첫 항목에 대한 답변으로 해석한다.

    `preview_opened`면 확정 대상이 `lines`가 아니라 `candidate_lines`다(6-3).
    """
    queue = list(state.get("pending_unclear") or [])
    _ocr_debug("_resume_unclear", step="enter", queue=len(queue))
    if not queue:
        # 상태 불일치 방어. 정상 흐름에서는 발생하지 않는다.
        _ocr_debug("_resume_unclear", step="branch", reason="empty_queue_fallback")
        return _ingest_new_lines(state)

    answer = (state.get("user_message") or "").strip()
    current = queue[0]
    _ocr_debug(
        "resolve_unclear_answer",
        step="call",
        answer=answer,
        raw=current.raw,
    )
    resolution = resolve_unclear_answer(answer, current)
    _ocr_debug(
        "resolve_unclear_answer",
        step="return",
        resolved=resolution.resolved is not None,
        reply=resolution.reply,
    )
    existing_lines = list(state.get("lines") or [])
    in_candidate_mode = bool(state.get("preview_opened"))
    merge_target = list(state.get("candidate_lines") or []) if in_candidate_mode else existing_lines

    if resolution.resolved is not None:
        merged, conflicts = merge_line_lists(merge_target, resolution.resolved)
        remaining = queue[1:]
        base: dict[str, Any] = {"lines": existing_lines, "pending_unclear": remaining}
        if in_candidate_mode:
            base["candidate_lines"] = merged
        else:
            base["lines"] = merged
        if conflicts:
            base["pending_kind"] = "field_conflict"
            base["pending_field_conflict"] = conflicts[0]
            base["reply"] = field_conflict_message(conflicts[0])
            _ocr_debug("_resume_unclear", step="branch", reason="field_conflict")
            return base
        if remaining:
            base["pending_kind"] = "unclear"
            base["reply"] = remaining[0].ask_message
            _ocr_debug("_resume_unclear", step="branch", reason="next_unclear")
            return base
        if in_candidate_mode:
            _ocr_debug("_resume_unclear", step="branch", reason="finalize_candidates")
            return {**base, **_finalize_candidates(merged, existing_lines)}
        base["pending_kind"] = None
        _ocr_debug("_resume_unclear", step="branch", reason="resolved")
        return base

    # 여전히 미확정 — 큐 첫 항목만 갱신하고 같은 질문(또는 갱신된 질문)을 반복한다.
    updated_first = resolution.updated_current or current
    _ocr_debug("_resume_unclear", step="branch", reason="still_unclear")
    return {
        "lines": existing_lines,
        "pending_unclear": [updated_first, *queue[1:]],
        "pending_kind": "unclear",
        "reply": resolution.reply,
    }


def _resume_field_conflict(state: OcrState) -> dict[str, Any]:
    """4-4b: pending_kind="field_conflict" 재진입 — 값 충돌 선택을 반영한다.

    `preview_opened`면 반영 대상이 `lines`가 아니라 `candidate_lines`다(6-3).
    """
    conflict = state.get("pending_field_conflict")
    _ocr_debug("_resume_field_conflict", step="enter", has_conflict=conflict is not None)
    if conflict is None:
        # 상태 불일치 방어.
        return _ingest_new_lines(state)

    answer = (state.get("user_message") or "").strip()
    existing_lines = list(state.get("lines") or [])
    in_candidate_mode = bool(state.get("preview_opened"))
    target = list(state.get("candidate_lines") or []) if in_candidate_mode else existing_lines

    _ocr_debug("apply_field_conflict_choice", step="call", text=answer, options=getattr(conflict, "options", None))
    applied = apply_field_conflict_choice(answer, target, conflict)
    _ocr_debug("apply_field_conflict_choice", step="return", applied=applied)
    if not applied:
        base: dict[str, Any] = {
            "lines": existing_lines,
            "pending_kind": "field_conflict",
            "pending_field_conflict": conflict,
            "reply": field_conflict_message(conflict),
        }
        if in_candidate_mode:
            base["candidate_lines"] = target
        else:
            base["lines"] = target
        return base

    pending_unclear = list(state.get("pending_unclear") or [])
    if pending_unclear:
        # turn.py의 after_lines_changed와 같은 우선순위: 충돌 해소 다음은 미매칭 큐.
        base = {
            "lines": existing_lines,
            "pending_unclear": pending_unclear,
            "pending_kind": "unclear",
            "pending_field_conflict": None,
            "reply": pending_unclear[0].ask_message,
        }
        if in_candidate_mode:
            base["candidate_lines"] = target
        else:
            base["lines"] = target
        return base

    if in_candidate_mode:
        result = _finalize_candidates(target, existing_lines)
        result["pending_field_conflict"] = None
        return result

    return {"lines": target, "pending_kind": None, "pending_field_conflict": None}


def _resume_name_confirm(state: OcrState) -> dict[str, Any]:
    """4-4b: pending_kind="name_confirm" 재진입 — 수량·단가 또는 부정.

    `preview_opened`면 확정 대상이 `lines`가 아니라 `candidate_lines`다(6-3).
    후보가 완결되면 `_finalize_candidates`가 바로 lines에 합친다(추가할까요? 생략).
    """
    name = state.get("pending_name_confirm")
    answer = (state.get("user_message") or "").strip()
    _ocr_debug("_resume_name_confirm", step="enter", name=name, user_message=answer)
    if not name:
        # 상태 불일치 방어.
        return _ingest_new_lines(state)

    denied = is_negative(answer)
    _ocr_debug("is_negative", text=answer, result=denied)
    if denied:
        _ocr_debug("_resume_name_confirm", step="branch", reason="cancelled")
        return {
            "pending_kind": None,
            "pending_name_confirm": None,
            "lines": list(state.get("lines") or []),
            "reply": name_confirm_cancel_message(name),
            # tool_2 전체확정 안내가 취소 문구를 덮지 않도록 턴을 여기서 끝낸다.
            "candidate_discarded": True,
        }

    qty = extract_qty_general(answer)
    price = extract_price_from_text(answer)
    unit = extract_qty_unit(answer)
    _ocr_debug("_resume_name_confirm", step="parsed", qty=qty, price=price, qty_unit=unit)
    if qty is None and price is None:
        # 유효 답을 통과하지 못한 채 들어온 방어. hold와 같은 확인 문구를 유지.
        _ocr_debug("_resume_name_confirm", step="branch", reason="no_qty_price_keep_ask")
        return {
            "pending_kind": "name_confirm",
            "pending_name_confirm": name,
            "reply": name_confirm_ask_message(name),
        }

    item = LineItem(name=name)
    if qty is not None:
        item.qty = qty
    if price is not None:
        item.unit_price = price
    if unit:
        item.qty_unit = unit
    item.recompute()

    existing_lines = list(state.get("lines") or [])
    in_candidate_mode = bool(state.get("preview_opened"))
    target = list(state.get("candidate_lines") or []) if in_candidate_mode else existing_lines
    # 기존 turn.py 로직과 동일하게, 병합 충돌 가능성은 여기서 보지 않는다
    # (신규 단어 확인 흐름이라 실제로는 거의 발생하지 않음).
    merged, _conflicts = merge_line_lists(target, [item])

    base: dict[str, Any] = {"lines": existing_lines, "pending_name_confirm": None}
    if in_candidate_mode:
        base["candidate_lines"] = merged
    else:
        base["lines"] = merged

    if item.qty is None or item.unit_price is None:
        result = check_completeness(merged)
        base["pending_kind"] = result.pending_kind or "fill_name"
        base["reply"] = result.message or ASK_QTY_PRICE_AMOUNT
        _ocr_debug("_resume_name_confirm", step="branch", reason="fill_name")
        return base

    if in_candidate_mode:
        result = _finalize_candidates(merged, existing_lines)
        result["pending_name_confirm"] = None
        _ocr_debug("_resume_name_confirm", step="branch", reason="finalize_candidates")
        return result

    base["pending_kind"] = None
    _ocr_debug("_resume_name_confirm", step="branch", reason="accepted")
    return base


def _resolve_add_confirm(state: OcrState) -> dict[str, Any]:
    """6-5/6-5a: "품목 N개를 추가할까요?" 답변 처리.

    긍정 → candidate_lines를 lines에 병합하고 확정. 부정 → 후보만 폐기하고
    확정 목록·미리보기는 그대로 유지, 채팅으로 복귀(candidate_discarded=True).
    """
    candidates = list(state.get("candidate_lines") or [])
    answer = (state.get("user_message") or "").strip()
    _ocr_debug("_resolve_add_confirm", step="enter", candidates=len(candidates), user_message=answer)
    if not candidates:
        # 상태 불일치 방어.
        return _ingest_new_lines(state)

    lines = list(state.get("lines") or [])

    yes = is_affirmative(answer)
    _ocr_debug("is_affirmative", text=answer, result=yes)
    if yes:
        merged, conflicts = merge_line_lists(lines, candidates)
        updates: dict[str, Any] = {
            "lines": merged,
            "candidate_lines": [],
            "candidate_discarded": False,
        }
        if conflicts:
            updates["pending_kind"] = "field_conflict"
            updates["pending_field_conflict"] = conflicts[0]
            updates["reply"] = field_conflict_message(conflicts[0])
            _ocr_debug("_resolve_add_confirm", step="branch", reason="field_conflict")
            return updates
        updates["pending_kind"] = None
        _ocr_debug("_resolve_add_confirm", step="branch", reason="accepted")
        return updates

    _ocr_debug("_resolve_add_confirm", step="branch", reason="discarded")
    return {
        "lines": lines,
        "candidate_lines": [],
        "candidate_discarded": True,
        "pending_kind": None,
    }


def tool_1_node(state: OcrState) -> dict[str, Any]:
    """0-2 Tool Node #1 — 원문→품목 추출 · 확정/미확정 분리 · 품목 합침.

    pending_kind로 신규 입력(6-3)과 되물음 재개(4-4b)를 나눈다.
    """
    pending_kind = state.get("pending_kind")
    _ocr_debug(
        "tool_1_node",
        step="enter",
        pending_kind=pending_kind,
        user_message=(state.get("user_message") or "").strip(),
    )
    if pending_kind == "add_confirm":
        _ocr_debug("tool_1_node", step="branch", handler="_resolve_add_confirm")
        updates = _resolve_add_confirm(state)
    elif pending_kind == "unclear":
        _ocr_debug("tool_1_node", step="branch", handler="_resume_unclear")
        updates = _resume_unclear(state)
    elif pending_kind == "field_conflict":
        _ocr_debug("tool_1_node", step="branch", handler="_resume_field_conflict")
        updates = _resume_field_conflict(state)
    elif pending_kind == "name_confirm":
        _ocr_debug("tool_1_node", step="branch", handler="_resume_name_confirm")
        updates = _resume_name_confirm(state)
    else:
        _ocr_debug("tool_1_node", step="branch", handler="_ingest_new_lines")
        updates = _ingest_new_lines(state)
    return _trace("tool_1_node", state, updates)


def tool_2_node(state: OcrState) -> dict[str, Any]:
    """0-3 Tool Node #2 — 필수값 완결 · 수량×단가 검산 · 되물음 생성 · 전체 확정 판정.

    미확정이 남으면 `followup_question`과 `pending_kind`를 채운다(4-1·4-2).
    `pending_kind`는 `check_completeness`가 실제로 내는 값(conflict/fill_name)만
    쓴다 — unclear/field_conflict/name_confirm은 Tool #1 소관(4-4 라우팅 테이블).

    `candidate_lines`가 있으면(6-3 진행 중) 검증 대상이 `lines`가 아니라
    `candidate_lines`다(완결되면 확정 병합 대신 add_confirm 되물음 —
    `_finalize_candidates` 재사용). `preview_opened`가 아니라 `candidate_lines`
    자체를 신호로 쓰는 이유: `preview_opened`는 한 번 True가 되면 계속 유지되므로,
    후보가 이미 lines로 합쳐진 뒤(6-6 재검증)에도 계속 후보 모드로 잘못 판단하게
    된다. `_route_after_tool_1`이 pending_kind가 남아있으면 tool_2로 안 보내도록
    고쳐져 있어서, tool_2가 pending_kind=None으로 들어올 때는 후보 처리가 이미
    끝난 상태임이 보장된다.

    `preview_opened`는 이 노드가 세팅하지 않는다. 원래 트리거인 "미리보기" 버튼
    액션(action=="preview")이 이제 어댑터(app/graph/ocr/service.py)에서 세션에
    직접 기록하고, 그 값을 그대로 실어서 invoke하므로 이 노드는 입력값을 읽기만
    한다(반환 dict에 넣지 않으면 그래프가 기존 값을 그대로 들고 있는다).
    """
    pending_kind = state.get("pending_kind")
    answer = (state.get("user_message") or "").strip()
    lines = list(state.get("lines") or [])
    candidates = state.get("candidate_lines")
    in_candidate_mode = bool(candidates)
    target = list(candidates or []) if in_candidate_mode else lines
    _ocr_debug(
        "tool_2_node",
        step="enter",
        pending_kind=pending_kind,
        user_message=answer,
        in_candidate_mode=in_candidate_mode,
        lines=len(target),
    )

    if pending_kind == "conflict":
        # "계산값으로 할까요?" 되물음 재개 — 동의하면 계산값으로 맞춘다.
        # 거부/애매하면 아무 것도 바꾸지 않고 아래에서 같은 판정을 다시 내린다.
        yes = is_affirmative(answer)
        _ocr_debug("is_affirmative", text=answer, result=yes)
        if yes:
            _ocr_debug("accept_calculated_amounts", step="call")
            accept_calculated_amounts(target)
    elif pending_kind == "fill_name":
        # "얼마인가요?" 되물음 재개 — 채울 대상 품목명은 완결성 검사가 다시 알려준다.
        target_name = check_completeness(target).pending_name
        _ocr_debug("check_completeness", step="fill_name", pending_name=target_name)
        if target_name:
            _ocr_debug("apply_fill", step="call", text=answer, pending_name=target_name)
            apply_fill(answer, target, target_name)

    if in_candidate_mode:
        _ocr_debug("tool_2_node", step="branch", reason="candidate_mode")
        return _trace("tool_2_node", state, _finalize_candidates(target, lines))

    _ocr_debug("check_completeness", step="call", lines=len(target))
    result = check_completeness(target)
    _ocr_debug(
        "check_completeness",
        step="return",
        ok=result.ok,
        pending_kind=result.pending_kind,
        message=result.message,
    )
    updates: dict[str, Any] = {"lines": target, "total": totals(target)}

    if not result.ok:
        updates["pending_kind"] = result.pending_kind
        updates["all_confirmed"] = False
        updates["followup_question"] = result.message or ""
        updates["reply"] = result.message or ""
        _ocr_debug("tool_2_node", step="branch", reason="incomplete", pending_kind=result.pending_kind)
        return _trace("tool_2_node", state, updates)

    updates["pending_kind"] = None
    updates["all_confirmed"] = True
    updates["followup_question"] = ""
    updates["reply"] = KIND_NOT_SELECTED_REPLY
    _ocr_debug("tool_2_node", step="branch", reason="all_confirmed")
    return _trace("tool_2_node", state, updates)


def tool_3_node(state: OcrState) -> dict[str, Any]:
    """0-4 Tool Node #3 — 수정 해석 · 품목 확인 · 반영 후 #2.

    1차 구현 범위는 수량 조정뿐이다. 단가 변경·품목 삭제 요청은 반영하지 않고
    안내만 하고 턴을 끝낸다. 재검증은 `check_completeness`를 직접 호출한다
    (`tool_2_node`로 재진입하지 않음 — 7-2 결정사항).
    """
    user_message = (state.get("user_message") or "").strip()
    _ocr_debug("tool_3_node", step="enter", user_message=user_message, pending_kind=state.get("pending_kind"))
    unsupported = is_unsupported_edit(user_message)
    _ocr_debug("is_unsupported_edit", text=user_message, result=unsupported)
    if unsupported:
        _ocr_debug("tool_3_node", step="branch", reason="unsupported_edit")
        return _trace("tool_3_node", state, {"reply": EDIT_UNSUPPORTED_GUIDE, "pending_kind": None})

    lines = list(state.get("lines") or [])
    pending_kind = state.get("pending_kind")

    if pending_kind == "ask_item":
        # 4-4b: "어떤 품목의 수량을 고칠까요?" 되물음 재개 — 저장해둔 수량 +
        # 이번 답의 품목명을 합쳐 다시 시도한다.
        name = guess_item_name(user_message)
        qty = state.get("pending_qty")
        _ocr_debug("guess_item_name", text=user_message, name=name, pending_qty=qty)
        if not name or qty is None:
            _ocr_debug("tool_3_node", step="branch", reason="ask_item_missing_name_or_qty")
            return _trace(
                "tool_3_node",
                state,
                {"pending_kind": "ask_item", "pending_qty": qty, "reply": ASK_WHICH_ITEM},
            )
        edit_text = f"{name} 수량 {qty}개"
    else:
        edit_text = user_message

    _ocr_debug("apply_natural_edit", step="call", edit_text=edit_text)
    updated_lines, msg = apply_natural_edit(edit_text, lines)
    _ocr_debug("apply_natural_edit", step="return", msg=msg)

    if msg == ASK_WHICH_ITEM:
        qty = state.get("pending_qty") if pending_kind == "ask_item" else extract_qty_from_text(user_message)
        _ocr_debug("tool_3_node", step="branch", reason="ask_which_item")
        return _trace(
            "tool_3_node",
            state,
            {
                "lines": updated_lines,
                "pending_kind": "ask_item",
                "pending_qty": qty,
                "reply": ASK_WHICH_ITEM,
            },
        )

    # 수량 반영 완료 — check_completeness로 재검증(tool_2_node와 같은 함수, 같은 판정 패턴).
    _ocr_debug("check_completeness", step="call", lines=len(updated_lines))
    result = check_completeness(updated_lines)
    updates: dict[str, Any] = {
        "lines": updated_lines,
        "total": totals(updated_lines),
        "pending_qty": None,
    }
    if not result.ok:
        updates["pending_kind"] = result.pending_kind
        updates["followup_question"] = result.message or ""
        updates["all_confirmed"] = False
        updates["reply"] = f"{msg}\n{result.message}" if result.message else msg
        _ocr_debug("tool_3_node", step="branch", reason="incomplete_after_edit")
        return _trace("tool_3_node", state, updates)

    updates["pending_kind"] = None
    updates["all_confirmed"] = True
    updates["followup_question"] = ""
    updates["reply"] = msg
    _ocr_debug("tool_3_node", step="branch", reason="edit_applied")
    return _trace("tool_3_node", state, updates)
