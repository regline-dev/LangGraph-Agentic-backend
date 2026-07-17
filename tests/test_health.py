"""Phase 0 — /health 엔드포인트 계약 테스트."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_status() -> None:
    """서버 생존 확인용 /health는 200과 status=ok를 반환한다."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
