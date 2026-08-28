"""POST /ocr/turn HTTP 계약. Vision은 주입."""

from fastapi.testclient import TestClient

from app.graph.ocr.service import OcrGraphTurnService, get_ocr_graph_turn_service
from app.main import app
from app.ocr.session import OcrSessionStore
from app.ocr.turn import OcrTurnService, get_ocr_turn_service
from app.tools.ocr_receipt import (
    UNREAD_NO_FIELDS,
    UNREAD_NO_TEXT,
    UNREAD_VISION,
    name_confirm_ask_message,
    name_confirm_cancel_message,
)

client = TestClient(app)


def test_ocr_turn_text_and_clear() -> None:
    service = OcrTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_turn_service] = lambda: service
    try:
        res = client.post(
            "/ocr/turn",
            json={"session_id": "http1", "text": "A품목 10개 단가 500000원"},
            headers={"X-Admin-User-Id": "regline"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["lines"][0]["name"] == "A품목"
        assert body["total"] == 5_000_000
        cleared = client.post("/ocr/session/clear", json={"session_id": "http1"})
        assert cleared.status_code == 200
        assert cleared.json()["lines"] == []
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_chitchat_no_unread() -> None:
    service = OcrTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_turn_service] = lambda: service
    try:
        res = client.post("/ocr/turn", json={"session_id": "http2", "text": "안녕하세요"})
        assert res.status_code == 200
        assert res.json()["unread"] is False
        assert "못 읽었습니다" not in res.json()["reply"]
    finally:
        app.dependency_overrides.clear()


# --- 3-1/3-2: OCR_USE_GRAPH=1일 때 그래프 경로가 레거시와 같은 응답 스키마로 동작하는지 ---


def test_ocr_turn_graph_message_confirms_receipt(monkeypatch) -> None:
    """action="message" — 그래프 invoke로 품목 확정(레거시 test_ocr_turn_text_and_clear와 동일 입력)."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        res = client.post(
            "/ocr/turn",
            json={"session_id": "g1", "text": "A품목 10개 단가 500000원"},
            headers={"X-Admin-User-Id": "regline"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["lines"][0]["name"] == "A품목"
        assert body["total"] == 5_000_000
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_followup_question_flow(monkeypatch) -> None:
    """되물음 흐름 — 단가 누락(fill_name) → 되물음 → 답변 → 확정(레거시 test_missing_price_then_fill과 동일)."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        asked = client.post("/ocr/turn", json={"session_id": "g2", "text": "A품목 10개"})
        assert asked.status_code == 200
        assert "단가" in asked.json()["reply"]

        filled = client.post("/ocr/turn", json={"session_id": "g2", "text": "500000원"})
        assert filled.status_code == 200
        assert filled.json()["total"] == 5_000_000
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_select_kind(monkeypatch) -> None:
    """action="select_kind" — 그래프를 타지 않고 레거시 로직에 위임되는지."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        client.post("/ocr/turn", json={"session_id": "g3", "text": "A품목 10개 단가 500000원"})
        res = client.post(
            "/ocr/turn",
            json={"session_id": "g3", "action": "select_kind", "kind_id": "receipt"},
        )
        assert res.status_code == 200
        assert res.json()["kind_id"] == "receipt"
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_preview(monkeypatch) -> None:
    """action="preview" — 그래프를 타지 않고 preview_opened/action_enabled가 레거시와 동일하게 채워지는지."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        client.post("/ocr/turn", json={"session_id": "g4", "text": "A품목 10개 단가 500000원"})
        client.post(
            "/ocr/turn", json={"session_id": "g4", "action": "select_kind", "kind_id": "receipt"}
        )
        res = client.post("/ocr/turn", json={"session_id": "g4", "action": "preview"})
        assert res.status_code == 200
        body = res.json()
        assert body["preview_opened"] is True
        assert "save" in body["action_enabled"]
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_first_confirmation_reply_matches_legacy(monkeypatch) -> None:
    """버그1 재현 ①: 최초 전체 확정 시 reply가 비지 않아야 한다.
    지금은 활성 kind가 1개(영수증)뿐이라 자동 선택까지 함께 확인한다."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        res = client.post("/ocr/turn", json={"session_id": "g6", "text": "커피 2개 3000원"})
        assert res.status_code == 200
        body = res.json()
        assert body["kind_id"] == "receipt"
        assert body["reply"] == (
            "커피, 2개, 단가 3,000원, 총 6,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "미리보기를 눌러주세요"
        )
        assert body["raw_text"] == "커피 2개 3000원"
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_fill_name_resume_reply_matches_legacy(monkeypatch) -> None:
    """버그1/2 재현 ②: 되물음(fill_name) 답변으로 확정되는 두 번째 호출의 reply/raw_text."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        asked = client.post("/ocr/turn", json={"session_id": "g7", "text": "커피 2개"})
        assert asked.json()["raw_text"] == "커피 2개"

        filled = client.post("/ocr/turn", json={"session_id": "g7", "text": "3000원"})
        assert filled.status_code == 200
        body = filled.json()
        assert body["kind_id"] == "receipt"
        assert body["reply"] == (
            "커피, 2개, 단가 3,000원, 총 6,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "미리보기를 눌러주세요"
        )
        assert body["total"] == 6000
        # fill_name 답변("3000원")은 신규 품목 인식이 아니므로 raw_text는 그대로 유지된다.
        assert body["raw_text"] == "커피 2개"
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_interrupt_prior_reply_and_just_filled_summary(monkeypatch) -> None:
    """인터럽트 안내는 prior_reply, 되물음 재개 확정은 이번 품목만 요약."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        client.post(
            "/ocr/turn",
            json={"session_id": "g11", "text": "A4용지 2개 단가 20000원 금액 50000원"},
        )
        interrupted = client.post("/ocr/turn", json={"session_id": "g11", "text": "율무차 추가"})
        body = interrupted.json()
        assert "확정했습니다" in body["prior_reply"]
        assert "율무차" in body["reply"]
        assert "확정했습니다" not in body["reply"]

        filled = client.post("/ocr/turn", json={"session_id": "g11", "text": "2개 4000원"})
        assert filled.json()["reply"] == (
            "율무차, 2개, 단가 4,000원, 총 8,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "미리보기를 눌러주세요"
        )
        names = {row["name"] for row in filled.json()["lines"]}
        assert "A4용지" in names
        assert "율무차" in names
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_auto_selects_kind_when_only_one_enabled(monkeypatch) -> None:
    """신규 기능: 활성 kind가 정확히 1개(영수증)면 전체 확정 시 kind_id를 자동 세팅하고
    preview_ready까지 True가 된다 (버튼 클릭 없이)."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        res = client.post("/ocr/turn", json={"session_id": "g9", "text": "커피 2개 3000원"})
        assert res.status_code == 200
        body = res.json()
        assert body["kind_id"] == "receipt"
        assert body["preview_ready"] is True
        assert "preview" in body["action_enabled"]
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_no_auto_select_when_multiple_kinds_enabled(monkeypatch) -> None:
    """활성 kind가 2개 이상이면 자동 선택하지 않고 수동(버튼 클릭) 그대로 유지된다."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    from app.graph.ocr import service as graph_service_module

    monkeypatch.setattr(
        graph_service_module,
        "DOCUMENT_KINDS",
        [
            {"id": "quote", "label": "견적서", "enabled": True},
            {"id": "receipt", "label": "영수증", "enabled": True},
        ],
    )
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        res = client.post("/ocr/turn", json={"session_id": "g10", "text": "커피 2개 3000원"})
        assert res.status_code == 200
        body = res.json()
        assert body["kind_id"] is None
        assert body["reply"] == (
            "커피, 2개, 단가 3,000원, 총 6,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "문서 종류를 선택한 뒤 미리보기를 눌러 주세요."
        )
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_add_confirm_yes_reply_matches_legacy(monkeypatch) -> None:
    """미리보기(kind_id 있음) 이후 완결 품목은 추가 확인 없이 바로 요약한다."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        client.post("/ocr/turn", json={"session_id": "g8", "text": "커피 2개 3000원"})
        client.post(
            "/ocr/turn", json={"session_id": "g8", "action": "select_kind", "kind_id": "receipt"}
        )
        client.post("/ocr/turn", json={"session_id": "g8", "action": "preview"})

        added = client.post("/ocr/turn", json={"session_id": "g8", "text": "우유 2개 1500원"})
        assert added.status_code == 200
        body = added.json()
        assert body["reply"] == (
            "우유, 2개, 단가 1,500원, 총 3,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "미리보기를 눌러주세요"
        )
        assert body["total"] == 9000
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_image_confirms_receipt(monkeypatch) -> None:
    """2-1~2-4: 이미지 업로드 → Vision(mock) → raw_text로 그래프 전달 → 확정.
    레거시 test_ocr_turn.py의 test_typed_data_is_read_data와 같은 내용을 이미지로 넣는다."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(
        store=OcrSessionStore(), vision_fn=lambda _b: "커피 2개 3000원"
    )
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        res = client.post(
            "/ocr/turn",
            json={"session_id": "gi1", "image_base64": "YQ==", "filename": "a.png", "mime": "image/png"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["lines"][0]["name"] == "커피"
        assert body["total"] == 6000
        # 활성 kind가 1개(영수증)뿐이라 자동 선택돼 "미리보기를 눌러 주세요." 문구가 나온다.
        assert body["kind_id"] == "receipt"
        assert body["reply"] == (
            "커피, 2개, 단가 3,000원, 총 6,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "미리보기를 눌러주세요"
        )
        assert body["raw_text"] == "커피 2개 3000원"
        assert body["unread"] is False
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_image_fail_three_reasons(monkeypatch) -> None:
    """2-3: Vision 실패/텍스트 없음/필드 없음 3가지 오류 — 레거시 test_image_fail_three_reasons와 동일 입력."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    try:
        empty_service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
        app.dependency_overrides[get_ocr_graph_turn_service] = lambda: empty_service
        empty_res = client.post(
            "/ocr/turn",
            json={"session_id": "gi2", "image_base64": "YQ==", "filename": "a.png", "mime": "image/png"},
        )
        assert empty_res.json()["reply"] == UNREAD_NO_TEXT
        assert empty_res.json()["unread"] is True
        assert empty_res.json()["lines"] == []

        fields_service = OcrGraphTurnService(
            store=OcrSessionStore(), vision_fn=lambda _b: "상호만 있음"
        )
        app.dependency_overrides[get_ocr_graph_turn_service] = lambda: fields_service
        fields_res = client.post(
            "/ocr/turn",
            json={"session_id": "gi3", "image_base64": "YQ==", "filename": "a.png", "mime": "image/png"},
        )
        assert fields_res.json()["reply"] == UNREAD_NO_FIELDS
        assert fields_res.json()["unread"] is True

        def boom(_b: bytes) -> str:
            raise RuntimeError("down")

        vision_error_service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=boom)
        app.dependency_overrides[get_ocr_graph_turn_service] = lambda: vision_error_service
        vision_res = client.post(
            "/ocr/turn",
            json={"session_id": "gi4", "image_base64": "YQ==", "filename": "a.png", "mime": "image/png"},
        )
        assert vision_res.json()["reply"] == UNREAD_VISION
        assert vision_res.json()["unread"] is True
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_clear(monkeypatch) -> None:
    """action="clear" — 세션이 완전히 비워지고, 이후 그래프 message 턴도 빈 상태로 시작하는지."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    shared_store = OcrSessionStore()
    graph_service = OcrGraphTurnService(store=shared_store, vision_fn=lambda _b: "")
    legacy_service = OcrTurnService(store=shared_store, vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: graph_service
    app.dependency_overrides[get_ocr_turn_service] = lambda: legacy_service
    try:
        client.post("/ocr/turn", json={"session_id": "g5", "text": "A품목 10개 단가 500000원"})
        cleared = client.post("/ocr/session/clear", json={"session_id": "g5"})
        assert cleared.status_code == 200
        assert cleared.json()["lines"] == []

        again = client.post("/ocr/turn", json={"session_id": "g5", "text": "안녕하세요"})
        assert again.json()["lines"] == []
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_name_confirm_qty_price_then_summary(monkeypatch) -> None:
    """단어 하나 → 수량·단가 → 바로 요약. 추가할까요? 없음."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        client.post("/ocr/turn", json={"session_id": "g12", "text": "커피 2개 3000원"})
        client.post("/ocr/turn", json={"session_id": "g12", "action": "preview"})

        asked = client.post("/ocr/turn", json={"session_id": "g12", "text": "율무차"})
        assert asked.json()["reply"] == name_confirm_ask_message("율무차")

        filled = client.post("/ocr/turn", json={"session_id": "g12", "text": "2잔 4000원"})
        body = filled.json()
        assert body["reply"] == (
            "율무차, 2잔, 단가 4,000원, 총 8,000원 입니다.\n"
            "내용을 확인하세요.\n"
            "미리보기를 눌러주세요"
        )
        names = {row["name"] for row in body["lines"]}
        assert names == {"커피", "율무차"}
        assert "추가할까요" not in body["reply"]
    finally:
        app.dependency_overrides.clear()


def test_ocr_turn_graph_name_confirm_deny_keeps_existing(monkeypatch) -> None:
    """부정은 후보만 취소하고 기존 품목은 남긴다."""
    monkeypatch.setenv("OCR_USE_GRAPH", "1")
    service = OcrGraphTurnService(store=OcrSessionStore(), vision_fn=lambda _b: "")
    app.dependency_overrides[get_ocr_graph_turn_service] = lambda: service
    try:
        client.post("/ocr/turn", json={"session_id": "g13", "text": "커피 2개 3000원"})
        client.post("/ocr/turn", json={"session_id": "g13", "action": "preview"})
        client.post("/ocr/turn", json={"session_id": "g13", "text": "율무차"})

        denied = client.post("/ocr/turn", json={"session_id": "g13", "text": "아니요"})
        body = denied.json()
        assert body["reply"] == name_confirm_cancel_message("율무차")
        assert [row["name"] for row in body["lines"]] == ["커피"]
    finally:
        app.dependency_overrides.clear()
