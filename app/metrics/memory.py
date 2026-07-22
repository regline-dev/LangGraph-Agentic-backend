"""세션별 직전 우화 제목 + MBTI (단기 메모리)."""

from __future__ import annotations


class FableSessionMemory:
    """프로세스 메모리 — session_id → 최근 우화 제목 / MBTI."""

    def __init__(self) -> None:
        self._last_title: dict[str, str] = {}
        self._mbti: dict[str, str] = {}

    def get(self, session_id: str | None) -> str | None:
        """직전 우화 제목 (기존 API 호환)."""
        return self.get_title(session_id)

    def set(self, session_id: str | None, title: str) -> None:
        """직전 우화 제목 저장 (기존 API 호환)."""
        self.set_title(session_id, title)

    def get_title(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        return self._last_title.get(session_id.strip()) or None

    def set_title(self, session_id: str | None, title: str) -> None:
        cleaned_session = (session_id or "").strip()
        cleaned_title = (title or "").strip()
        if not cleaned_session or not cleaned_title:
            return
        self._last_title[cleaned_session] = cleaned_title

    def get_mbti(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        return self._mbti.get(session_id.strip()) or None

    def set_mbti(self, session_id: str | None, mbti: str) -> None:
        cleaned_session = (session_id or "").strip()
        cleaned = (mbti or "").strip().upper()
        if not cleaned_session or not cleaned:
            return
        self._mbti[cleaned_session] = cleaned


# 운영 기본 인스턴스 (테스트는 새 인스턴스 주입)
default_fable_memory = FableSessionMemory()
