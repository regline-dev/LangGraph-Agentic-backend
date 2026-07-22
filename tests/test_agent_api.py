"""순번 15~16 — POST /agent/chat HTTP 계약 테스트."""

from fastapi.testclient import TestClient

from app.graph.runtime import get_agent_runner
from app.main import app


def _fake_runner(question: str) -> dict:
    return {
        "answer": f"답변: {question}",
        "citations": [
            {
                "source_file": "sample.pdf",
                "page": 1,
                "snippet": "Annual leave is fifteen days.",
                "score": 0.87,
            }
        ],
    }


client = TestClient(app)


def test_agent_chat_returns_answer_and_citations() -> None:
    """성공 시 answer + citations 계약을 지킨다."""
    app.dependency_overrides[get_agent_runner] = lambda: _fake_runner
    try:
        response = client.post("/agent/chat", json={"question": "연차는 며칠?"})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"].startswith("답변:")
        assert len(body["citations"]) == 1
        assert body["citations"][0]["source_file"] == "sample.pdf"
        assert body["citations"][0]["page"] == 1
        assert "snippet" in body["citations"][0]
        assert body["citations"][0]["score"] == 0.87
        assert body["similarity"] == 0.87
    finally:
        app.dependency_overrides.clear()


def test_agent_chat_rejects_empty_question() -> None:
    """빈 question은 422."""
    app.dependency_overrides[get_agent_runner] = lambda: _fake_runner
    try:
        response = client.post("/agent/chat", json={"question": ""})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
