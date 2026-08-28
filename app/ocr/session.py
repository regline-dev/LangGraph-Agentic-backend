"""OCR 전용 단기 기억. FAQ/PDF 우화 메모리와 분리."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.tools.ocr_receipt import FieldConflict, LineItem


@dataclass
class OcrSessionState:
    lines: list[LineItem] = field(default_factory=list)
    pending_fill_name: str | None = None
    pending_ask_item: bool = False
    pending_qty: int | None = None
    pending_conflict: bool = False
    pending_field_conflict: FieldConflict | None = None
    pending_unclear: list = field(default_factory=list)
    pending_name_confirm: str | None = None
    raw_text: str = ""
    doc_total_ocr: int | None = None
    kind_id: str | None = None
    preview_opened: bool = False
    # --- 그래프(app/graph/ocr) 전용 필드 ---
    # 레거시 경로(OcrTurnService)는 pending_conflict/pending_ask_item/pending_fill_name
    # 처럼 종류별 bool/str을 쓰지만, 그래프는 종류를 하나로 합친 pending_kind를 쓴다.
    # 같은 세션 저장소(OcrSessionStore)를 그대로 공유하기 위해 필드만 얹었다 —
    # 레거시 코드는 이 필드들을 읽거나 쓰지 않는다.
    pending_kind: str | None = None
    candidate_lines: list[LineItem] = field(default_factory=list)


class OcrSessionStore:
    def __init__(self) -> None:
        self._by_session: dict[str, OcrSessionState] = {}

    def get(self, session_id: str | None) -> OcrSessionState:
        key = (session_id or "").strip() or "_"
        if key not in self._by_session:
            self._by_session[key] = OcrSessionState()
        return self._by_session[key]

    def clear(self, session_id: str | None) -> None:
        key = (session_id or "").strip() or "_"
        self._by_session.pop(key, None)


default_ocr_store = OcrSessionStore()
