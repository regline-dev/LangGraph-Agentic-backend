"""OCR StateGraph가 주고받는 상태.

기준: Docs/20260827_OCR_LLM_Tool_이미지_작업사항_수정본_2차.md 0번 섹션
의도·되물음 종류는 app/tools/ocr_receipt.py의 타입을 그대로 쓴다 (정의 이원화 방지).
"""

from __future__ import annotations

from typing import TypedDict

from app.tools.ocr_receipt import FieldConflict, Intent, LineItem, PendingKind, UnclearLine


class OcrState(TypedDict, total=False):
    """한 턴(`/ocr/turn`) 동안 노드들이 채우고 읽는 상태."""

    # --- 입력 ---
    user_message: str  # 이번 턴 채팅 입력
    raw_text: str  # Vision 원문 또는 텍스트 첫 입력 원문

    # --- 0-1 LLM 라우터 결과 ---
    # chitchat / data / edit / fill / amount_only
    intent: Intent

    # --- 0-2 Tool #1: 확정/미확정 분리 ---
    # OcrSessionState와 같은 타입을 쓴다. dict 변환은 응답 직전에만
    # (lines_as_dicts / unclear_as_dicts).
    lines: list[LineItem]  # 확정 품목
    pending_unclear: list[UnclearLine]  # 미확정 품목

    # --- 6-3~6-5 미리보기 이후 추가 후보 (아직 lines에 합치지 않은 상태) ---
    candidate_lines: list[LineItem]
    # 6-5a: "추가할까요?"에 아니오 → 후보만 버리고 확정 목록·미리보기는 유지
    candidate_discarded: bool

    # --- 0-3 Tool #2 ---
    all_confirmed: bool  # 전체 확정 판정
    followup_question: str  # 되물음 문구
    total: int  # 수량×단가 검산 합계 (totals)

    # 4-4: 되물음 답변은 LLM 라우터를 재경유하지 않는다. 어떤 되물음이었는지에 따라
    # 다음 턴의 진입 Tool이 달라지므로 종류를 그대로 들고 있는다 (_route_entry 참고).
    pending_kind: PendingKind | None
    # pending_kind == "field_conflict"일 때 재개에 필요한 대상 (OcrSessionState와 동일 역할)
    pending_field_conflict: FieldConflict | None
    # pending_kind == "name_confirm"일 때 재개에 필요한 후보 품목명
    pending_name_confirm: str | None
    # pending_kind == "ask_item"일 때 재개에 필요한 수량 (품목명만 다음 턴에 옴)
    pending_qty: int | None

    # 되물음 중 무관 요청으로 기본값을 확정했을 때, 같은 턴 안내를 뒤에 붙이기 위한 문구.
    interrupt_notice: str

    # 5-2 / 7-2: 이미 미리보기가 떠 있으면 "(자동) 영수증 기본선택"을 다시 타지 않고
    # 미리보기만 직접 갱신한다 (사용자가 바꾼 문서종류가 초기화되는 것을 막기 위함).
    preview_ready: bool
    # 6-3: 미리보기가 이미 열렸는지 — True면 새 품목은 lines에 바로 합치지 않고
    # candidate_lines에 쌓아 6-5 확인을 받는다. 트리거는 "미리보기" 버튼 액션
    # (action=="preview")이며, 그래프 자신은 이 값을 세팅하지 않는다 — 어댑터
    # (app/graph/ocr/service.py)가 세션(OcrSessionState.preview_opened)에서
    # 읽어 그대로 실어 넘긴다(3-1/3-2).
    preview_opened: bool

    # --- 출력 ---
    reply: str
