"""PDF 관리 API의 사람이 읽는 다줄 로그."""

from __future__ import annotations

from datetime import datetime, timezone


def log_pdf_api(
    *,
    api: str,
    admin_user_id: str | None,
    result: str,
    template_id: str | None = None,
    reason: str | None = None,
) -> None:
    """요청·성공·실패를 한 번의 다줄 로그 호출로 출력한다."""
    lines = [
        f"[{datetime.now(timezone.utc).isoformat()}] api={api}",
        f"  admin_user_id={(admin_user_id or 'guest').strip() or 'guest'}",
        f"  template_id={(template_id or '-').strip() or '-'}",
        f"  result={result}",
    ]
    if reason:
        lines.append(f"  reason={reason}")
    print("\n".join(lines), flush=True)
