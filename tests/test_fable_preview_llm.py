"""POST /fable/preview-llm — 미리보기 시점 LLM 1회."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_preview_llm_rejects_empty_body() -> None:
    response = client.post("/fable/preview-llm", json={"body_text": "  "})
    assert response.status_code == 400


def test_preview_llm_aesop_returns_score_only(monkeypatch) -> None:
    from app.api import fable as fable_api

    def _fake_score(body_text, **kwargs):
        _ = body_text, kwargs
        return {
            "title": "늑대와 어린양",
            "fun": 3,
            "violence": 1,
            "moral_clarity": 5,
            "ending_tone": "해피",
            "tags": ["교훈"],
        }

    monkeypatch.setattr(fable_api, "score_fable_with_llm", _fake_score)
    response = client.post(
        "/fable/preview-llm",
        json={
            "body_text": "늑대가 물을 마시러 왔다.",
            "type_code": "aesop",
            "type_name": "이솝우화",
        },
        headers={"X-Admin-User-Id": "regline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "aesop"
    assert body["items"] == []
    assert body["score"]["fun"] == 3
    assert body["score"]["ending_tone"] == "해피"


def test_preview_llm_custom_returns_items(monkeypatch) -> None:
    from app.fable_pdf import typed_scorer

    def _fake_draft(body_text, type_name, **kwargs):
        _ = body_text, type_name, kwargs
        return {
            "title": "북촌 찻길",
            "items": [{"name": "오픈", "value": "2024년 3월", "chart": "none"}],
            "tags": [],
        }

    monkeypatch.setattr(typed_scorer, "draft_typed_items_with_llm", _fake_draft)
    response = client.post(
        "/fable/preview-llm",
        json={
            "body_text": "북촌 찻길\n오픈: 2024년 3월",
            "type_code": "CAFE",
            "type_name": "카페",
        },
        headers={"X-Admin-User-Id": "regline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "custom"
    assert body["items"][0]["name"] == "오픈"
    assert body["items"][0]["value"] == "2024년 3월"
    assert body["score"] is None


def test_preview_llm_colon_left_only_as_items() -> None:
    """콜론 왼쪽만 구성 항목. LLM 흉내 없이 미리보기 API로 확인."""
    body_text = (
        "문서제목\n\n"
        "구역: 가, 나, 다\n"
        "가는 대기 많고, 나는 비고, 다는 주말만 연다.\n\n"
        "상품: 하나, 둘, 셋\n"
        "하나는 8,000원이고 둘은 9,000원, 셋은 6,000원이다.\n\n"
        "시간대: 낮, 밤\n"
        "낮은 8,400원, 밤은 12,000원이다.\n\n"
        "여기는 소개 문단이라 구성 항목이 아니다.\n"
    )
    response = client.post(
        "/fable/preview-llm",
        json={
            "body_text": body_text,
            "type_code": "custom_doc",
            "type_name": "문서",
        },
        headers={"X-Admin-User-Id": "regline"},
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body["items"]]
    assert names == ["구역", "상품", "시간대"]
    assert "가" not in names
    assert "하나" not in names
    assert "소개" not in "".join(item["value"] for item in body["items"])
