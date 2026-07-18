"""Agent 실행 — Groq 그래프 + Qdrant 검색을 묶어 /agent/chat에 제공한다."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import get_settings
from app.graph.workflow import build_groq_agent_graph, run_agent
from app.qdrant_factory import create_qdrant_client
from app.tools.search_documents import search_documents
from ingest.index_documents import FakeEmbedder

# question → {answer, citations}
AgentRunner = Callable[[str], dict[str, Any]]


def create_qdrant_search_fn() -> Callable[[str], list[dict[str, Any]]]:
    """설정값으로 Qdrant 검색 함수를 만든다 (임베딩은 당분간 Fake)."""
    settings = get_settings()
    client = create_qdrant_client(settings)
    embedder = FakeEmbedder(dimension=32)
    collection = settings.qdrant_collection

    def search_fn(query: str) -> list[dict[str, Any]]:
        return search_documents(
            query,
            client=client,
            collection_name=collection,
            embedder=embedder,
            top_k=3,
        )

    return search_fn


def run_agent_chat(question: str) -> dict[str, Any]:
    """운영 기본 경로: Groq 판단 + Qdrant 검색."""
    graph = build_groq_agent_graph(search_fn=create_qdrant_search_fn())
    state = run_agent(graph, question=question)
    return {
        "answer": state.get("answer") or "",
        "citations": list(state.get("citations") or []),
    }


def get_agent_runner() -> AgentRunner:
    """FastAPI Depends용 — 테스트에서 override 가능."""
    return run_agent_chat
