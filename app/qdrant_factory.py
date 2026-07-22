"""Qdrant 클라이언트 생성 — 로컬 PATH 우선, 없으면 HOST:PORT.

Chroma 로컬 persist / LangGraph `QDRANT_PATH` 와 같은 패턴.

로컬 path 모드는 프로세스당 클라이언트 1개만 가능 → `get_shared_qdrant_client` 사용.
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from app.config import Settings, get_settings

# 로컬 PATH 잠금 충돌 방지 — 앱 수명 동안 공유
_shared_client: QdrantClient | None = None
_shared_key: str | None = None


def create_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """설정에 따라 로컬 path 또는 원격 host:port 클라이언트를 만든다.

    - `QDRANT_PATH` 가 있으면 → `QdrantClient(path=...)` (Docker 불필요)
    - 비어 있으면 → `QdrantClient(host=..., port=...)` (Docker/서버)

    주의: 로컬 path는 동시 인스턴스 불가. 운영 경로는 `get_shared_qdrant_client`를 쓴다.
    """
    cfg = settings or get_settings()
    local_path = (cfg.qdrant_path or "").strip()

    if local_path:
        storage = Path(local_path)
        storage.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(storage))

    return QdrantClient(host=cfg.qdrant_host, port=cfg.qdrant_port)


def _client_key(settings: Settings) -> str:
    local_path = (settings.qdrant_path or "").strip()
    if local_path:
        return f"path:{Path(local_path).resolve()}"
    return f"host:{settings.qdrant_host}:{settings.qdrant_port}"


def get_shared_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """프로세스 내 공유 클라이언트 (로컬 PATH 이중 open 방지)."""
    global _shared_client, _shared_key

    cfg = settings or get_settings()
    key = _client_key(cfg)
    if _shared_client is not None and _shared_key == key:
        return _shared_client

    if _shared_client is not None:
        try:
            _shared_client.close()
        except Exception:  # noqa: BLE001
            pass
        _shared_client = None
        _shared_key = None

    _shared_client = create_qdrant_client(cfg)
    _shared_key = key
    return _shared_client


def reset_shared_qdrant_client() -> None:
    """테스트용 — 공유 클라이언트 해제."""
    global _shared_client, _shared_key
    if _shared_client is not None:
        try:
            _shared_client.close()
        except Exception:  # noqa: BLE001
            pass
    _shared_client = None
    _shared_key = None
