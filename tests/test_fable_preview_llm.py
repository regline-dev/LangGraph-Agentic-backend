"""POST /fable/preview-llm — 이솝 채점 / 커스텀은 있는 이름만 채움."""

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


def test_preview_llm_custom_without_configs_does_not_invent_items() -> None:
    """구성 이름 없이 미리보기 LLM을 쳐도 원문에서 항목을 만들지 않는다."""
    response = client.post(
        "/fable/preview-llm",
        json={
            "body_text": "구역: 가, 나\n가는 대기 많다.",
            "type_code": "custom_doc",
            "type_name": "문서",
        },
        headers={"X-Admin-User-Id": "regline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "custom"
    assert body["items"] == []
    assert body.get("groups") in (None, {})


def test_preview_llm_custom_fills_named_groups_only(monkeypatch) -> None:
    from app.api import fable as fable_api

    def _fake_typed(body_text, profile, **kwargs):
        _ = body_text, kwargs
        names = [str(c.get("group_name") or "") for c in (profile.configs or [])]
        assert names == ["프로그램"]
        return {
            "title": "한강별빛축제",
            "groups": {"프로그램": {"요약": "개막식 8/15"}},
            "subtitles": {},
            "tags": [],
        }

    monkeypatch.setattr(fable_api.typed_scorer, "score_typed_with_llm", _fake_typed)
    response = client.post(
        "/fable/preview-llm",
        json={
            "body_text": "한강별빛축제\n개막식 8/15",
            "type_code": "FESTIVAL",
            "type_name": "축제안내",
            "configs": [{"group_name": "프로그램", "values_text": ""}],
        },
        headers={"X-Admin-User-Id": "regline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "custom"
    assert body["groups"]["프로그램"]["요약"] == "개막식 8/15"
    assert body["items"][0]["name"] == "프로그램"
    assert body["items"][0]["value"] == "개막식 8/15"
    assert body["score"] is None


def test_preview_llm_custom_fills_named_subtitles(monkeypatch) -> None:
    """구성이 없어도 보낸 서브타이틀 제목에만 값을 채운다."""
    from app.api import fable as fable_api

    def _fake_typed(body_text, profile, **kwargs):
        _ = body_text, kwargs
        titles = [str(s.get("title") or "") for s in (profile.subtitles or [])]
        assert titles == ["요약"]
        assert list(profile.configs or []) == []
        return {
            "title": "한강별빛축제",
            "groups": {},
            "subtitles": {"요약": "여의도에서 사흘간 열린다."},
            "tags": [],
        }

    monkeypatch.setattr(fable_api.typed_scorer, "score_typed_with_llm", _fake_typed)
    response = client.post(
        "/fable/preview-llm",
        json={
            "body_text": "한강별빛축제\n여의도한강공원",
            "type_code": "FESTIVAL",
            "type_name": "축제안내",
            "subtitles": [{"title": "요약", "mode": "llm", "content": ""}],
        },
        headers={"X-Admin-User-Id": "counsel"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "custom"
    assert body["groups"] in (None, {})
    assert body["subtitles"]["요약"] == "여의도에서 사흘간 열린다."
    assert body["items"] == []
