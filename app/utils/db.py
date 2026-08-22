"""MariaDB 연결 — 템플릿 등록 DB(chatbot, admin_backend_python과 공유).

admin_backend_python/src/utils/db.py와 같은 연결 풀 패턴.
"""

from __future__ import annotations

import inspect
import os

import mariadb

from app.config import get_settings

_pool: mariadb.ConnectionPool | None = None


def get_connection_pool() -> mariadb.ConnectionPool:
    """MariaDB 연결 풀 반환 (싱글톤)."""
    global _pool
    if _pool is None:
        settings = get_settings()
        try:
            _pool = mariadb.ConnectionPool(
                pool_name="langgraph_agentic_backend_pool",
                pool_size=10,
                pool_reset_connection=True,
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
            )
            print("[DB] 연결 풀 생성 완료 (pool_size=10)")
        except Exception as e:  # noqa: BLE001
            print(f"[DB] 연결 풀 생성 실패: {e}")
            raise
    return _pool


def get_db_connection() -> mariadb.Connection:
    """연결 풀에서 커넥션 하나 반환."""
    pool = get_connection_pool()
    return pool.get_connection()


def _get_caller_info() -> tuple[str, str]:
    """호출한 파일명·함수명 반환 — 쿼리 로그에 어디서 호출했는지 표시용."""
    try:
        stack = inspect.stack()
        for frame_info in stack:
            filename = frame_info.filename
            if "db.py" not in filename:
                return (os.path.basename(filename), frame_info.function)
        return ("unknown", "unknown")
    except Exception:  # noqa: BLE001
        return ("unknown", "unknown")
