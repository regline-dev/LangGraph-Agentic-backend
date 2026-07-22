"""유사도 score 전파 — search → tool citations → /agent/chat similarity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.graph.nodes import make_tool_node
from app.graph.runtime import get_agent_runner
from app.graph.workflow import build_agent_graph, run_agent
from app.main import app
from app.tools.search_documents import search_documents
from ingest.index_documents import FakeEmbedder, ingest_pdf, store_upload
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"
client = TestClient(app)


def test_search_documents_includes_numeric_score(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    qdrant = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    saved = store_upload(ensure_sample_pdf(FIXTURES_DIR), uploads_dir=uploads)
    ingest_pdf(
        saved,
        client=qdrant,
        collection_name="pdf_chunks",
        embedder=embedder,
        uploads_dir=uploads,
    )
    results = search_documents(
        "annual leave",
        client=qdrant,
        collection_name="pdf_chunks",
        embedder=embedder,
        top_k=2,
    )
    assert results
    assert "score" in results[0]
    assert isinstance(results[0]["score"], float)


def test_tool_node_copies_score_into_citations() -> None:
    def search_fn(_query: str) -> list[dict[str, Any]]:
        return [
            {
                "page_content": "본문",
                "metadata": {"source_file": "a.pdf", "page": 2, "chunk_id": "a-1"},
                "score": 0.81,
            }
        ]

    node = make_tool_node(search_fn)
    out = node(
        {
            "question": "q",
            "search_query": "q",
            "tool_call_count": 0,
            "observations": [],
            "citations": [],
            "need_search": True,
            "answer": "",
        }
    )
    assert out["citations"][0]["score"] == 0.81
    assert out["citations"][0]["source_file"] == "a.pdf"


def test_agent_graph_citations_carry_score() -> None:
    def decide(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("observations"):
            return {"need_search": False, "search_query": "", "answer": "근거 있음"}
        return {"need_search": True, "search_query": "leave", "answer": ""}

    def search_fn(_query: str) -> list[dict[str, Any]]:
        return [
            {
                "page_content": "fifteen days",
                "metadata": {"source_file": "sample.pdf", "page": 1, "chunk_id": "1"},
                "score": 0.66,
            }
        ]

    graph = build_agent_graph(decide_fn=decide, search_fn=search_fn)
    result = run_agent(graph, question="연차는?")
    assert result["citations"][0]["score"] == 0.66


def test_agent_api_similarity_is_max_citation_score() -> None:
    def runner(_question: str) -> dict[str, Any]:
        return {
            "answer": "ok",
            "citations": [
                {"source_file": "a.pdf", "page": 1, "snippet": "x", "score": 0.4},
                {"source_file": "b.pdf", "page": 2, "snippet": "y", "score": 0.92},
            ],
        }

    app.dependency_overrides[get_agent_runner] = lambda: runner
    try:
        response = client.post("/agent/chat", json={"question": "테스트"})
        assert response.status_code == 200
        body = response.json()
        assert body["citations"][0]["score"] == 0.4
        assert body["citations"][1]["score"] == 0.92
        assert body["similarity"] == 0.92
    finally:
        app.dependency_overrides.clear()


def test_agent_api_missing_score_defaults_to_zero() -> None:
    def runner(_question: str) -> dict[str, Any]:
        return {
            "answer": "규칙 경로",
            "citations": [{"source_file": "c.pdf", "page": 1, "snippet": "원문"}],
        }

    app.dependency_overrides[get_agent_runner] = lambda: runner
    try:
        response = client.post("/agent/chat", json={"question": "내용"})
        assert response.status_code == 200
        body = response.json()
        assert body["citations"][0]["score"] == 0.0
        assert body["similarity"] == 0.0
    finally:
        app.dependency_overrides.clear()


def test_pdf_ui_score_line_policy() -> None:
    """PDF agent_chat만: vector면 유사도, meta면 유사도 숨김. FAQ 정책과 분리."""

    def line_for(status: str, retrieval: str, similarity: float) -> str:
        if status == "agent_chat":
            if retrieval == "vector" and similarity > 0:
                return f"유사도: {similarity:.3f}"
            return "출처: 메타/문서"
        return f"유사도: {similarity:.3f}"

    assert line_for("agent_chat", "meta", 0.0) == "출처: 메타/문서"
    assert line_for("agent_chat", "vector", 0.634) == "유사도: 0.634"
    # FAQ 등 다른 status는 0이어도 유사도 표기 유지
    assert line_for("similar_match", "vector", 0.0) == "유사도: 0.000"
