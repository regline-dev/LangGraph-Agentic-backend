"""Qdrant 클라이언트 생성 — 로컬 PATH 우선, 없으면 HOST:PORT.

Chroma 로컬 persist / LangGraph `QDRANT_PATH` 와 같은 패턴.
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from app.config import Settings, get_settings


def create_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """설정에 따라 로컬 path 또는 원격 host:port 클라이언트를 만든다.

    - `QDRANT_PATH` 가 있으면 → `QdrantClient(path=...)` (Docker 불필요)
    - 비어 있으면 → `QdrantClient(host=..., port=...)` (Docker/서버)
    """
    cfg = settings or get_settings()
    local_path = (cfg.qdrant_path or "").strip()

    if local_path:
        storage = Path(local_path)
        storage.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(storage))

    return QdrantClient(host=cfg.qdrant_host, port=cfg.qdrant_port)
