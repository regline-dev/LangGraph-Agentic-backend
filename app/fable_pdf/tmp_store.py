"""생성 PDF 임시 경로 · TTL 청소."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def make_tmp_pdf_path(*, tmp_dir: Path, fable_id: int) -> Path:
    """충돌 방지용 임시 PDF 경로: {id}_{timestamp}_{uuid}.pdf."""
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return tmp_dir / f"{fable_id}_{stamp}_{short_id}.pdf"


def cleanup_expired_tmp_pdfs(
    *,
    tmp_dir: Path,
    ttl_seconds: int = 24 * 3600,
) -> list[str]:
    """TTL이 지난 .pdf 를 삭제하고 삭제된 파일명 목록을 반환한다."""
    tmp_dir = Path(tmp_dir)
    if not tmp_dir.is_dir():
        return []

    now = time.time()
    deleted: list[str] = []
    for path in tmp_dir.glob("*.pdf"):
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age < ttl_seconds:
            continue
        try:
            path.unlink()
            deleted.append(path.name)
        except OSError:
            pass
    return deleted
