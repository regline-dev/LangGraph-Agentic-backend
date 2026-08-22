"""POST /fable/draft-configs — 커스텀 구성 초안(LLM 1회) HTTP 계약."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_draft_configs_rejects_empty_body() -> None:
    response = client.post("/fable/draft-configs", json={"body_text": "  "})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_draft_configs_rejects_aesop_type() -> None:
    """이솝은 구성 초안 API를 쓰지 않는다."""
    response = client.post(
        "/fable/draft-configs",
        json={
            "body_text": "늑대가 물을 마시러 왔다.",
            "type_code": "aesop",
            "type_name": "이솝우화",
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "이솝" in detail


def test_draft_configs_returns_items(monkeypatch) -> None:
    from app.fable_pdf import typed_scorer

    def _fake_draft(body_text, type_name, **kwargs):
        _ = body_text, type_name, kwargs
        return {
            "title": "한강별빛축제",
            "items": [{"name": "기간", "value": "8월", "chart": "none"}],
            "tags": ["축제"],
        }

    monkeypatch.setattr(typed_scorer, "draft_typed_items_with_llm", _fake_draft)
    response = client.post(
        "/fable/draft-configs",
        json={
            "body_text": "한강별빛축제\n기간: 8월",
            "type_code": "local_festival",
            "type_name": "지방축제 안내",
        },
        headers={"X-Admin-User-Id": "regline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "한강별빛축제"
    assert body["items"][0]["name"] == "기간"
    assert body["items"][0]["value"] == "8월"
    assert body["items"][0]["chart"] == "none"
