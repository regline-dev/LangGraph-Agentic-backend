"""Qdrant 클라이언트 — QDRANT_PATH 로컬 / HOST:PORT 서버 분기."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.qdrant_factory import (
    create_qdrant_client,
    get_shared_qdrant_client,
    reset_shared_qdrant_client,
)


def test_create_qdrant_client_uses_local_path_when_set(tmp_path: Path) -> None:
    """QDRANT_PATH가 있으면 Docker 없이 로컬 폴더 모드로 연다 (Chroma persist 패턴)."""
    storage = tmp_path / "qdrant_local"
    settings = Settings(
        qdrant_path=str(storage),
        qdrant_host="should-not-use.example",
        qdrant_port=9999,
        qdrant_collection="pdf_chunks",
    )

    client = create_qdrant_client(settings)
    try:
        # 로컬 모드면 디렉터리가 생기고 컬렉션 API가 동작한다
        assert storage.exists()
        names = {item.name for item in client.get_collections().collections}
        assert isinstance(names, set)
    finally:
        client.close()


def test_create_qdrant_client_uses_host_port_when_path_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """QDRANT_PATH가 비면 기존처럼 host:port(Docker/서버)로 연결한다."""
    created: dict[str, object] = {}

    class FakeQdrantClient:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)

    monkeypatch.setattr("app.qdrant_factory.QdrantClient", FakeQdrantClient)

    settings = Settings(
        qdrant_path="",
        qdrant_host="localhost",
        qdrant_port=6333,
        qdrant_collection="pdf_chunks",
    )
    create_qdrant_client(settings)

    assert created.get("host") == "localhost"
    assert created.get("port") == 6333
    assert "path" not in created


def test_create_qdrant_client_trims_blank_path_as_server_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """공백만 있는 PATH도 서버 모드로 본다."""
    created: dict[str, object] = {}

    class FakeQdrantClient:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)

    monkeypatch.setattr("app.qdrant_factory.QdrantClient", FakeQdrantClient)

    settings = Settings(qdrant_path="   ", qdrant_host="127.0.0.1", qdrant_port=6333)
    create_qdrant_client(settings)

    assert created.get("host") == "127.0.0.1"
    assert "path" not in created


def test_get_shared_qdrant_client_reuses_same_instance(tmp_path: Path) -> None:
    """로컬 PATH는 공유 클라이언트 1개만 쓴다 (이중 open → 502 방지)."""
    reset_shared_qdrant_client()
    storage = tmp_path / "qdrant_shared"
    settings = Settings(
        qdrant_path=str(storage),
        qdrant_host="unused",
        qdrant_port=1,
        qdrant_collection="pdf_chunks",
    )
    try:
        first = get_shared_qdrant_client(settings)
        second = get_shared_qdrant_client(settings)
        assert first is second
    finally:
        reset_shared_qdrant_client()
