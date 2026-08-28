"""문서종류 활성 여부 — 화면 설정과 같은 id. 타입명 문자열 if 금지."""

from __future__ import annotations

from typing import Any

# frontend_react/src/ocr/ocrTabConfig.js OCR_DOCUMENT_KINDS 와 동일 구조
DOCUMENT_KINDS: list[dict[str, Any]] = [
    {"id": "quote", "label": "견적서", "enabled": False},
    {"id": "statement", "label": "거래명세서", "enabled": False},
    {"id": "receipt", "label": "영수증", "enabled": True},
    {"id": "invoice", "label": "청구서", "enabled": False},
]


def kind_by_id(kind_id: str | None) -> dict[str, Any] | None:
    if not kind_id:
        return None
    return next((row for row in DOCUMENT_KINDS if row["id"] == kind_id), None)
