"""순번 23 — Hetzner compose에 LangGraph-Agentic-backend 규약."""

from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# 모노레포 워크스페이스: LangGraph-Agentic-backend/../docker-compose.hetzner.yml
COMPOSE_PATH = BACKEND_ROOT.parent / "docker-compose.hetzner.yml"


@pytest.fixture(scope="module")
def compose_text() -> str:
    if not COMPOSE_PATH.is_file():
        pytest.skip(f"모노레포 compose 없음: {COMPOSE_PATH}")
    return COMPOSE_PATH.read_text(encoding="utf-8")


def test_compose_has_langgraph_agentic_on_8010(compose_text: str) -> None:
    assert "langgraph_agentic:" in compose_text
    assert "LangGraph-Agentic-backend" in compose_text
    assert "8010:8010" in compose_text or '"8010:8010"' in compose_text


def test_compose_has_qdrant_and_agent_points_to_it(compose_text: str) -> None:
    assert "qdrant:" in compose_text
    assert "QDRANT_HOST=qdrant" in compose_text or "QDRANT_HOST: qdrant" in compose_text
    assert "6333" in compose_text


def test_compose_removes_legacy_regline_hub(compose_text: str) -> None:
    # Vercel로 이전 — Hetzner :3003 서비스 금지
    assert "regline_hub:" not in compose_text
    assert "container_name: regline-hub" not in compose_text


def test_env_hetzner_example_lists_required_keys() -> None:
    path = BACKEND_ROOT / ".env.hetzner.example"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for key in (
        "APP_PORT",
        "GROQ_API_KEY",
        "QDRANT_PATH",
        "QDRANT_HOST",
        "QDRANT_PORT",
        "QDRANT_COLLECTION",
        "EMBEDDING_BACKEND",
    ):
        assert key in text, f"{key} 가 .env.hetzner.example 에 있어야 한다"
    assert "8010" in text
