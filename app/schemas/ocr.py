"""OCR 턴 HTTP 스키마."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OcrTurnRequest(BaseModel):
    session_id: str | None = None
    text: str = ""
    image_base64: str | None = None
    filename: str | None = None
    mime: str | None = None
    action: str = "message"
    kind_id: str | None = None


class OcrTurnResponse(BaseModel):
    reply: str = ""
    lines: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    kinds_selectable: bool = False
    kind_id: str | None = None
    preview_ready: bool = False
    preview_opened: bool = False
    unread: bool = False
    action_enabled: list[str] = Field(default_factory=list)
    kinds: list[dict[str, Any]] = Field(default_factory=list)
    raw_text: str = ""
    unclear_lines: list[dict[str, Any]] = Field(default_factory=list)
    prior_reply: str = ""


class OcrClearRequest(BaseModel):
    session_id: str | None = None
