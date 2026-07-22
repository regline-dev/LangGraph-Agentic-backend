"""UI(localhost:3001) → Agent(:8010) CORS 헤더 계약."""

from fastapi.testclient import TestClient

from app.graph.runtime import get_agent_runner
from app.main import app

client = TestClient(app)

_FRONTEND_ORIGIN = "http://localhost:3001"


def _fake_runner(question: str) -> dict:
    return {"answer": f"답변: {question}", "citations": []}


def test_cors_preflight_does_not_pair_wildcard_with_credentials() -> None:
    """브라우저 preflight: ACAO=* 이면 credentials=true 금지."""
    response = client.options(
        "/agent/chat",
        headers={
            "Origin": _FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin in ("*", _FRONTEND_ORIGIN)
    allow_credentials = (response.headers.get("access-control-allow-credentials") or "").lower()
    if allow_origin == "*":
        assert allow_credentials != "true"


def test_cors_post_response_readable_from_frontend_origin() -> None:
    """실제 POST 응답도 * + credentials=true 충돌이 없어야 한다."""
    app.dependency_overrides[get_agent_runner] = lambda: _fake_runner
    try:
        response = client.post(
            "/agent/chat",
            json={"question": "너 누구야?"},
            headers={"Origin": _FRONTEND_ORIGIN},
        )
        assert response.status_code == 200
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin in ("*", _FRONTEND_ORIGIN)
        allow_credentials = (response.headers.get("access-control-allow-credentials") or "").lower()
        if allow_origin == "*":
            assert allow_credentials != "true"
    finally:
        app.dependency_overrides.clear()
