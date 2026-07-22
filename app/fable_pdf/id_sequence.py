"""우화 ID 자동 채번 — data/fable_id_seq.txt (파일 잠금)."""

from __future__ import annotations

import os
import time
from pathlib import Path


def next_fable_id(seq_path: Path, *, max_wait_seconds: float = 5.0) -> int:
    """
    시퀀스 파일의 마지막 번호에 +1 한 값을 반환하고 저장한다.
    동시 요청은 잠금 파일(O_EXCL)로 직렬화한다.
    """
    seq_path = Path(seq_path)
    seq_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = seq_path.with_name(seq_path.name + ".lock")

    deadline = time.monotonic() + max_wait_seconds
    lock_fd: int | None = None
    while True:
        try:
            # 잠금 파일이 없을 때만 생성 → 다른 프로세스는 대기
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"우화 ID 잠금 대기 초과: {lock_path}") from None
            time.sleep(0.05)

    try:
        current = 0
        if seq_path.exists():
            raw = seq_path.read_text(encoding="utf-8").strip()
            if raw:
                try:
                    current = int(raw)
                except ValueError:
                    current = 0
        nxt = current + 1
        seq_path.write_text(str(nxt), encoding="utf-8")
        return nxt
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
