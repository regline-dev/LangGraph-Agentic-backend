"""OCR 한 턴: 의도 → Tool #1/#2/#3. 필드는 여기만 판단."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

from app.ocr.kinds import DOCUMENT_KINDS, kind_by_id
from app.ocr.session import OcrSessionState, OcrSessionStore, default_ocr_store
from app.ocr.vision import VisionFn, extract_text_google_vision
from app.tools.ocr_receipt import (
    AMOUNT_ONLY_GUIDE,
    ASK_ITEM_FIELDS,
    ASK_QTY_PRICE_AMOUNT,
    ASK_WHICH_ITEM,
    CHITCHAT_GUIDE,
    IMAGE_ONLY,
    KIND_READY,
    READ_OK_PREFIX,
    Completeness,
    LineItem,
    UnclearLine,
    accept_calculated_amounts,
    apply_field_conflict_choice,
    apply_fill,
    apply_natural_edit,
    check_completeness,
    classify_intent,
    completeness,
    extract_doc_total_ocr,
    extract_price_from_text,
    extract_qty_from_text,
    extract_qty_general,
    field_conflict_message,
    guess_item_name,
    image_fail_reason,
    is_affirmative,
    is_greeting,
    is_image_upload,
    lines_as_dicts,
    merge_line_lists,
    parse_lines_from_text,
    parse_raw_with_unclear,
    totals,
    unclear_ask_message,
    unclear_as_dicts,
)


DEBUG_ONOFF = os.getenv("DEBUG_ONOFF") == "1"


@dataclass
class OcrTurnResult:
    reply: str
    lines: list[dict[str, Any]]
    total: int
    kinds_selectable: bool
    kind_id: str | None
    preview_ready: bool
    preview_opened: bool
    unread: bool
    action_enabled: list[str]
    kinds: list[dict[str, Any]]
    raw_text: str = ""
    unclear_lines: list[dict[str, Any]] | None = None
    prior_reply: str = ""


def _debug(message: str) -> None:
    if DEBUG_ONOFF:
        print(f"[ocr_turn] {message}", flush=True)


def pending_from_completeness(state: OcrSessionState, result: Completeness) -> None:
    """되물음 종류를 판정 결과에서 그대로 받는다 (되물음 문구를 다시 읽지 않는다)."""
    state.pending_conflict = result.pending_kind == "conflict"
    state.pending_fill_name = (
        result.pending_name if result.pending_kind == "fill_name" else None
    )


def _action_enabled(state: OcrSessionState, complete: bool) -> list[str]:
    enabled: list[str] = []
    if complete and state.kind_id and not state.pending_unclear:
        enabled.append("preview")
    if state.preview_opened:
        enabled.extend(["save", "download"])
    return enabled


def _result(
    state: OcrSessionState,
    reply: str,
    *,
    unread: bool = False,
) -> OcrTurnResult:
    blocked = bool(state.pending_unclear)
    complete, _ = completeness(state.lines, doc_total_ocr=state.doc_total_ocr)
    complete = complete and not blocked
    kinds_selectable = bool(state.lines) and not unread and not blocked
    return OcrTurnResult(
        reply=reply,
        lines=lines_as_dicts(state.lines),
        total=totals(state.lines),
        kinds_selectable=kinds_selectable,
        kind_id=state.kind_id,
        preview_ready=bool(complete and state.kind_id),
        preview_opened=state.preview_opened,
        unread=unread,
        action_enabled=_action_enabled(state, complete),
        kinds=DOCUMENT_KINDS,
        raw_text=state.raw_text or "",
        unclear_lines=unclear_as_dicts(state.pending_unclear),
        prior_reply="",
    )


def after_lines_changed(state: OcrSessionState) -> str:
    if state.pending_field_conflict is not None:
        return field_conflict_message(state.pending_field_conflict)
    if state.pending_unclear:
        first: UnclearLine = state.pending_unclear[0]
        return first.ask_message
    result = check_completeness(state.lines, doc_total_ocr=state.doc_total_ocr)
    if not result.ok:
        pending_from_completeness(state, result)
        return result.message or CHITCHAT_GUIDE
    state.pending_fill_name = None
    state.pending_conflict = False
    state.pending_ask_item = False
    if not state.kind_id:
        return f"{READ_OK_PREFIX}\n{KIND_READY}"
    return f"{READ_OK_PREFIX}\n미리보기를 눌러 주세요."


def merge_into_state(state: OcrSessionState, parsed: list) -> None:
    merged, conflicts = merge_line_lists(state.lines, parsed)
    state.lines = merged
    if conflicts:
        state.pending_field_conflict = conflicts[0]
    else:
        state.pending_field_conflict = None


def ingest_raw(state: OcrSessionState, raw: str) -> None:
    """원문 저장 + 확정/미매칭 분류. 미매칭은 큐에 적재."""
    if raw:
        if state.raw_text:
            state.raw_text = f"{state.raw_text}\n{raw}"
        else:
            state.raw_text = raw
    confirmed, unclear = parse_raw_with_unclear(raw)
    doc_total = extract_doc_total_ocr(raw)
    if doc_total is not None:
        state.doc_total_ocr = doc_total
    if confirmed:
        merge_into_state(state, confirmed)
    if unclear:
        state.pending_unclear.extend(unclear)


class OcrTurnService:
    def __init__(
        self,
        store: OcrSessionStore | None = None,
        vision_fn: VisionFn | None = None,
    ) -> None:
        self._store = store or default_ocr_store
        self._vision = vision_fn or extract_text_google_vision

    def clear(self, session_id: str | None) -> OcrTurnResult:
        self._store.clear(session_id)
        empty = OcrSessionState()
        return _result(empty, "", unread=False)

    def handle(
        self,
        *,
        session_id: str | None,
        text: str = "",
        image_base64: str | None = None,
        filename: str | None = None,
        mime: str | None = None,
        action: str = "message",
        kind_id: str | None = None,
    ) -> OcrTurnResult:
        state = self._store.get(session_id)

        if action == "clear":
            return self.clear(session_id)

        if action == "select_kind":
            kind = kind_by_id(kind_id)
            if not kind or not kind["enabled"]:
                return _result(state, "아직 준비중인 문서입니다.")
            if not state.lines:
                return _result(state, "먼저 품목·수량·단가를 입력하거나 사진을 올려 주세요.")
            if state.pending_unclear:
                return _result(state, after_lines_changed(state))
            state.kind_id = kind["id"]
            reply = after_lines_changed(state)
            return _result(state, reply)

        if action == "preview":
            if state.pending_unclear:
                return _result(state, after_lines_changed(state))
            result = check_completeness(state.lines, doc_total_ocr=state.doc_total_ocr)
            if not result.ok:
                pending_from_completeness(state, result)
                return _result(state, result.message or "필수 항목을 채워 주세요.")
            if not state.kind_id:
                return _result(state, KIND_READY)
            state.preview_opened = True
            return _result(state, "미리보기입니다. 저장하거나 다운로드할 수 있습니다.")

        if image_base64 or filename:
            if not is_image_upload(filename, mime):
                return _result(state, IMAGE_ONLY)
            return self._handle_image(state, image_base64 or "")

        return self._handle_text(state, text or "")

    def _handle_image(self, state: OcrSessionState, image_base64: str) -> OcrTurnResult:
        vision_error = False
        ocr_text = ""
        try:
            raw = base64.b64decode(image_base64)
            ocr_text = self._vision(raw)
            if DEBUG_ONOFF:
                _debug(f"vision_text={ocr_text[:500]!r}")
        except Exception as exc:  # noqa: BLE001 — Vision 경계
            vision_error = True
            _debug(f"vision_error={exc}")
        confirmed, unclear = (
            parse_raw_with_unclear(ocr_text) if not vision_error else ([], [])
        )
        fail = image_fail_reason(
            vision_error=vision_error,
            ocr_text=ocr_text,
            lines=confirmed,
        )
        # 확정은 없어도 미매칭이 있으면 "못 읽음"이 아니라 되물음
        if fail and not unclear:
            return _result(state, fail, unread=True)
        if ocr_text:
            if state.raw_text:
                state.raw_text = f"{state.raw_text}\n{ocr_text}"
            else:
                state.raw_text = ocr_text
        doc_total = extract_doc_total_ocr(ocr_text) if ocr_text else None
        if doc_total is not None:
            state.doc_total_ocr = doc_total
        if confirmed:
            merge_into_state(state, confirmed)
        if unclear:
            state.pending_unclear.extend(unclear)
        reply = after_lines_changed(state)
        if state.raw_text and "「" not in reply:
            reply = f"{READ_OK_PREFIX}\n{reply}" if READ_OK_PREFIX not in reply else reply
        return _result(state, reply)

    def _resolve_unclear(self, state: OcrSessionState, cleaned: str) -> OcrTurnResult:
        current: UnclearLine = state.pending_unclear[0]
        if is_affirmative(cleaned) and current.suggestion is not None:
            merge_into_state(state, [current.suggestion])
            state.pending_unclear.pop(0)
            return _result(state, after_lines_changed(state))

        parsed = parse_lines_from_text(cleaned)
        # _LINE으로 단가까지 확정 매칭된 경우만 "완전히 새로운 품목"으로 받아들인다.
        # 그렇지 않으면(예: "2box는 2개야") 엉뚱한 품목을 새로 만들지 말고,
        # 지금 제안 중인 품목에 대한 보정 답으로 본다.
        if any(item.unit_price is not None for item in parsed):
            merge_into_state(state, parsed)
            state.pending_unclear.pop(0)
            return _result(state, after_lines_changed(state))

        if current.suggestion is None:
            name = guess_item_name(current.raw)
            if name and not name[0].isdigit():
                current.suggestion = LineItem(name=name)

        if current.suggestion is not None:
            qty = extract_qty_general(cleaned)
            price = extract_price_from_text(cleaned)
            if qty is not None or price is not None:
                if qty is not None:
                    current.suggestion.qty = qty
                if price is not None:
                    current.suggestion.unit_price = price
                current.suggestion.recompute()
                if current.suggestion.qty is not None and current.suggestion.unit_price is not None:
                    merge_into_state(state, [current.suggestion])
                    state.pending_unclear.pop(0)
                    return _result(state, after_lines_changed(state))
                current.ask_message = unclear_ask_message(current.raw, current.suggestion)
                return _result(state, current.ask_message)

        return _result(state, current.ask_message)

    def _handle_text(self, state: OcrSessionState, text: str) -> OcrTurnResult:
        cleaned = (text or "").strip()
        if not cleaned:
            return _result(state, "내용을 입력해 주세요.")

        if state.pending_unclear:
            return self._resolve_unclear(state, cleaned)

        if state.pending_field_conflict is not None:
            ok_choice = apply_field_conflict_choice(
                cleaned, state.lines, state.pending_field_conflict
            )
            if not ok_choice:
                return _result(state, field_conflict_message(state.pending_field_conflict))
            state.pending_field_conflict = None
            return _result(state, after_lines_changed(state))

        if state.pending_conflict:
            if is_affirmative(cleaned):
                accept_calculated_amounts(state.lines)
                if state.doc_total_ocr is not None:
                    calc = totals(state.lines)
                    if state.doc_total_ocr != calc:
                        state.doc_total_ocr = calc
                state.pending_conflict = False
                return _result(state, after_lines_changed(state))
            ok, msg = completeness(state.lines, doc_total_ocr=state.doc_total_ocr)
            return _result(state, msg or "계산값으로 할까요?")

        if state.pending_ask_item:
            name = guess_item_name(cleaned)
            qty = state.pending_qty
            if not name or qty is None:
                return _result(state, ASK_WHICH_ITEM)
            state.lines, msg = apply_natural_edit(f"{name} 수량 {qty}개", state.lines)
            state.pending_ask_item = False
            state.pending_qty = None
            if msg == ASK_WHICH_ITEM:
                state.pending_ask_item = True
                state.pending_qty = qty
                return _result(state, ASK_WHICH_ITEM)
            follow = after_lines_changed(state)
            return _result(state, f"{msg}\n{follow}")

        if state.pending_fill_name:
            apply_fill(cleaned, state.lines, state.pending_fill_name)
            state.pending_fill_name = None
            return _result(state, after_lines_changed(state))

        if state.pending_name_confirm:
            name = state.pending_name_confirm
            state.pending_name_confirm = None
            if is_affirmative(cleaned):
                item = LineItem(name=name)
                qty = extract_qty_from_text(cleaned)
                price = extract_price_from_text(cleaned)
                if qty is not None:
                    item.qty = qty
                if price is not None:
                    item.unit_price = price
                item.recompute()
                merge_into_state(state, [item])
                if item.qty is None or item.unit_price is None:
                    state.pending_fill_name = name
                    return _result(state, ASK_QTY_PRICE_AMOUNT)
                return _result(state, after_lines_changed(state))
            return _result(state, ASK_ITEM_FIELDS)

        intent = classify_intent(cleaned, has_lines=bool(state.lines))
        _debug(f"intent={intent}")
        if intent == "amount_only":
            return _result(state, AMOUNT_ONLY_GUIDE)
        if intent == "chitchat":
            if is_greeting(cleaned):
                return _result(state, CHITCHAT_GUIDE)
            if len(cleaned.split()) == 1:
                state.pending_name_confirm = cleaned
                return _result(state, f"{cleaned}가 품목입니까?")
            return _result(state, ASK_ITEM_FIELDS)
        if intent == "edit":
            before = [item.qty for item in state.lines]
            state.lines, msg = apply_natural_edit(cleaned, state.lines)
            if msg == ASK_WHICH_ITEM:
                state.pending_ask_item = True
                state.pending_qty = extract_qty_from_text(cleaned)
                return _result(state, ASK_WHICH_ITEM)
            if [item.qty for item in state.lines] == before:
                return _result(state, msg)
            follow = after_lines_changed(state)
            return _result(state, f"{msg}\n{follow}")

        ingest_raw(state, cleaned)
        return _result(state, after_lines_changed(state))


def get_ocr_turn_service() -> OcrTurnService:
    return OcrTurnService()
