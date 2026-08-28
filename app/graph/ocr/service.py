"""OCR StateGraph를 `/ocr/turn`에 연결하는 어댑터 (3-1/3-2).

레거시 `app/ocr/turn.py`(`OcrTurnService`)는 그대로 두고, 이 모듈만 새로 추가한다.

세션 저장은 기존 `OcrSessionStore`(`app/ocr/session.py`의 `OcrSessionState`)를
그대로 쓴다. 그래프 전용 필드(`pending_kind`/`candidate_lines`)만 `OcrSessionState`에
얹었을 뿐, 나머지 필드(lines/pending_unclear/pending_field_conflict/
pending_name_confirm/pending_qty/preview_opened/kind_id/raw_text)는 레거시와
완전히 같은 필드를 공유한다 — 그래서 응답 변환은 레거시의 `_result()`를 그대로
재사용할 수 있다(신규 구현 금지, 스키마 동일성 보장).

action별 처리:
- "clear"/"select_kind"/"preview": 그래프를 타지 않는다. 이 세 액션은 그래프
  노드가 다루는 pending_kind/candidate_lines를 전혀 건드리지 않으므로, 같은
  세션을 공유하는 레거시 `OcrTurnService.handle()`에 그대로 위임한다.
- "message": 그래프를 invoke한다.
"""

from __future__ import annotations

import base64
from copy import deepcopy

from app.config import get_settings
from app.graph.ocr.nodes import KIND_NOT_SELECTED_REPLY, _ocr_debug
from app.graph.ocr.state import OcrState
from app.graph.ocr.workflow import build_ocr_graph
from app.ocr.kinds import DOCUMENT_KINDS
from app.ocr.session import OcrSessionState, OcrSessionStore, default_ocr_store
from app.ocr.turn import OcrTurnResult, OcrTurnService, _result
from app.ocr.vision import VisionFn, extract_text_google_vision
from app.tools.ocr_receipt import (
    IMAGE_ONLY,
    READ_OK_PREFIX,
    format_just_filled_preview_reply,
    image_fail_reason,
    is_image_upload,
    newly_completed_items,
    parse_raw_with_unclear,
)

# select_kind/preview/clear는 그래프 없이 레거시 로직을 그대로 위임 호출한다(중복 구현 금지).
_LEGACY_ONLY_ACTIONS = ("clear", "select_kind", "preview")

# turn.py의 after_lines_changed(134행)와 완전히 동일한 문구 — kind_id가 이미 있는
# 세션에서 tool_2_node의 기본 안내(KIND_NOT_SELECTED_REPLY)를 바꿔치기할 때 쓴다.
# ocr_receipt.py엔 이 문구를 담은 이름 있는 상수가 없어 turn.py 문자열을 그대로 복사했다.
_PREVIEW_READY_REPLY = f"{READ_OK_PREFIX}\n미리보기를 눌러 주세요."

_default_graph = build_ocr_graph()


def _debug(message: str) -> None:
    if get_settings().debug_onoff:
        print(f"[ocr_graph_service] {message}", flush=True)


def _session_to_ocr_state(
    session: OcrSessionState, *, user_message: str = "", raw_text: str = ""
) -> OcrState:
    return {
        "user_message": user_message,
        "raw_text": raw_text,
        "lines": list(session.lines),
        "pending_unclear": list(session.pending_unclear),
        "candidate_lines": list(session.candidate_lines),
        "pending_kind": session.pending_kind,
        "pending_field_conflict": session.pending_field_conflict,
        "pending_name_confirm": session.pending_name_confirm,
        "pending_qty": session.pending_qty,
        "preview_opened": session.preview_opened,
    }


def _auto_select_kind_id(session: OcrSessionState) -> None:
    """전체 확정 시 문서종류 자동 선택 (그래프 경로 전용, 레거시 turn.py는 미적용).

    활성(enabled) kind가 정확히 1개일 때만 자동 세팅한다. 지금은 영수증 하나뿐이라
    안전하지만, 나중에 견적서 등이 추가로 활성화돼 2개 이상이 되면 이 조건이
    저절로 꺼져서 수동 선택(버튼 클릭)으로 되돌아간다 — "receipt" 하드코딩 금지.
    """
    enabled_kinds = [row for row in DOCUMENT_KINDS if row["enabled"]]
    if len(enabled_kinds) == 1:
        session.kind_id = enabled_kinds[0]["id"]


def _finalize_reply(
    session: OcrSessionState,
    updated: dict,
    *,
    before_lines: list | None = None,
) -> str:
    """tool_2_node는 kind_id를 모르므로 "미선택" 기본 문구(KIND_NOT_SELECTED_REPLY)만
    낸다. 세션에 이미 kind_id가 있으면(turn.py의 after_lines_changed와 같은 분기)
    여기서 "미리보기를 눌러 주세요." 쪽으로 바꿔치기한다. kind_id가 아직 없으면
    활성 kind가 1개뿐인지 확인해서 자동 선택을 시도한다.

    이번 턴에 막 완결된 품목이 있으면 고정 「읽었어요」 대신 그 품목만 요약한다.
    """
    reply = updated.get("reply") or ""
    _ocr_debug(
        "_finalize_reply",
        step="enter",
        reply=reply,
        kind_id=session.kind_id,
        pending_kind=session.pending_kind,
    )
    if reply != KIND_NOT_SELECTED_REPLY:
        _ocr_debug("_finalize_reply", step="return", reason="pass_through")
        return reply
    if not session.kind_id:
        _ocr_debug("_auto_select_kind_id", step="call")
        _auto_select_kind_id(session)
        _ocr_debug("_auto_select_kind_id", step="return", kind_id=session.kind_id)
    after_lines = list(updated.get("lines") or session.lines)
    filled = newly_completed_items(list(before_lines or []), after_lines)
    _ocr_debug(
        "newly_completed_items",
        step="return",
        filled=len(filled),
        names=[item.name for item in filled],
    )
    if filled:
        summarized = format_just_filled_preview_reply(
            filled, kind_selected=bool(session.kind_id)
        )
        if summarized:
            _ocr_debug("_finalize_reply", step="return", reason="just_filled", reply=summarized)
            return summarized
    if session.kind_id:
        _ocr_debug("_finalize_reply", step="return", reason="preview_ready")
        return _PREVIEW_READY_REPLY
    _ocr_debug("_finalize_reply", step="return", reason="kind_not_selected")
    return reply


def _apply_ocr_state_to_session(session: OcrSessionState, updated: dict) -> None:
    session.lines = list(updated.get("lines", session.lines))
    session.pending_unclear = list(updated.get("pending_unclear", session.pending_unclear))
    session.candidate_lines = list(updated.get("candidate_lines", session.candidate_lines))
    session.pending_kind = updated.get("pending_kind")
    session.pending_field_conflict = updated.get("pending_field_conflict")
    session.pending_name_confirm = updated.get("pending_name_confirm")
    session.pending_qty = updated.get("pending_qty")
    session.preview_opened = bool(updated.get("preview_opened", session.preview_opened))


class OcrGraphTurnService:
    """`/ocr/turn`을 OCR StateGraph로 처리한다. `OcrTurnService`와 같은 인터페이스."""

    def __init__(
        self,
        store: OcrSessionStore | None = None,
        vision_fn: VisionFn | None = None,
        graph=None,
    ) -> None:
        self._store = store or default_ocr_store
        self._vision = vision_fn or extract_text_google_vision
        self._graph = graph or _default_graph
        self._legacy = OcrTurnService(store=self._store, vision_fn=self._vision)

    def clear(self, session_id: str | None) -> OcrTurnResult:
        return self._legacy.clear(session_id)

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
        if action in _LEGACY_ONLY_ACTIONS:
            _debug(f"delegate to legacy action={action}")
            return self._legacy.handle(
                session_id=session_id,
                text=text,
                image_base64=image_base64,
                filename=filename,
                mime=mime,
                action=action,
                kind_id=kind_id,
            )

        session = self._store.get(session_id)
        _ocr_debug(
            "OcrGraphTurnService.handle",
            step="enter",
            action=action,
            session_id=session_id,
            text=text,
            has_image=bool(image_base64 or filename),
            pending_kind=session.pending_kind,
        )

        if image_base64 or filename:
            if not is_image_upload(filename, mime):
                return _result(session, IMAGE_ONLY)
            return self._handle_image(session, image_base64 or "")

        return self._handle_text(session, text or "")

    def _handle_text(self, session: OcrSessionState, text: str) -> OcrTurnResult:
        cleaned = (text or "").strip()
        if not cleaned:
            return _result(session, "내용을 입력해 주세요.")
        before_lines = deepcopy(session.lines)
        ocr_state = _session_to_ocr_state(session, user_message=cleaned)
        _ocr_debug(
            "OcrGraphTurnService._handle_text",
            step="invoke",
            pending_kind=session.pending_kind,
            lines=len(session.lines),
            user_message=cleaned,
        )
        updated = self._graph.invoke(ocr_state)
        _ocr_debug(
            "OcrGraphTurnService._handle_text",
            step="invoke_done",
            pending_kind=updated.get("pending_kind"),
            intent=updated.get("intent"),
            reply=updated.get("reply"),
            interrupt_notice=updated.get("interrupt_notice"),
        )
        _apply_ocr_state_to_session(session, updated)
        # turn.py의 ingest_raw는 신규 품목 인식(intent=="data")일 때만 raw_text를
        # 누적한다(그 외 되물음 재개 등은 원문을 다시 쌓지 않음) — 그래프의 intent는
        # 이번 턴에 llm_router_node가 실제로 판정했을 때만 존재하므로 그대로 재사용.
        if updated.get("intent") == "data":
            session.raw_text = f"{session.raw_text}\n{cleaned}" if session.raw_text else cleaned
        result = _result(session, _finalize_reply(session, updated, before_lines=before_lines))
        result.prior_reply = (updated.get("interrupt_notice") or "").strip()
        return result

    def _handle_image(self, session: OcrSessionState, image_base64: str) -> OcrTurnResult:
        vision_error = False
        ocr_text = ""
        try:
            raw = base64.b64decode(image_base64)
            ocr_text = self._vision(raw)
        except Exception as exc:  # noqa: BLE001 — Vision 경계, turn.py의 _handle_image와 동일 처리
            vision_error = True
            _debug(f"vision_error={exc}")
        probe_confirmed, probe_unclear = (
            parse_raw_with_unclear(ocr_text) if not vision_error else ([], [])
        )
        fail = image_fail_reason(vision_error=vision_error, ocr_text=ocr_text, lines=probe_confirmed)
        if fail and not probe_unclear:
            return _result(session, fail, unread=True)
        if ocr_text:
            session.raw_text = f"{session.raw_text}\n{ocr_text}" if session.raw_text else ocr_text
        before_lines = deepcopy(session.lines)
        ocr_state = _session_to_ocr_state(session, raw_text=ocr_text)
        _ocr_debug(
            "OcrGraphTurnService._handle_image",
            step="invoke",
            pending_kind=session.pending_kind,
            raw_text=ocr_text,
            vision_error=vision_error,
        )
        updated = self._graph.invoke(ocr_state)
        _apply_ocr_state_to_session(session, updated)
        result = _result(session, _finalize_reply(session, updated, before_lines=before_lines))
        result.prior_reply = (updated.get("interrupt_notice") or "").strip()
        return result


def get_ocr_graph_turn_service() -> OcrGraphTurnService:
    return OcrGraphTurnService()
