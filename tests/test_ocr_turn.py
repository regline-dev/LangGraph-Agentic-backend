"""OCR 턴·Vision mock·중계 판단 없음 계약 테스트."""

from app.ocr.session import OcrSessionStore
from app.ocr.turn import OcrTurnService
from app.tools.ocr_receipt import ASK_ITEM_FIELDS, ASK_WHICH_ITEM, CHITCHAT_GUIDE, IMAGE_ONLY, UNREAD_NO_FIELDS, UNREAD_NO_TEXT, UNREAD_VISION


def _svc(vision=None) -> OcrTurnService:
    return OcrTurnService(store=OcrSessionStore(), vision_fn=vision)


def test_chitchat_does_not_add_lines() -> None:
    svc = _svc()
    out = svc.handle(session_id="s1", text="안녕하세요")
    assert out.lines == []
    assert out.unread is False
    assert CHITCHAT_GUIDE in out.reply


def test_typed_data_is_read_data() -> None:
    svc = _svc()
    out = svc.handle(session_id="s2", text="A품목 10개 단가 500000원")
    assert len(out.lines) == 1
    assert out.lines[0]["name"] == "A품목"
    assert out.total == 5_000_000
    assert out.kinds_selectable is True


def test_edit_asks_which_item_then_updates() -> None:
    svc = _svc()
    svc.handle(session_id="s3", text="A품목 10개 단가 500000원")
    ask = svc.handle(session_id="s3", text="수량 15개로 고쳐줘")
    assert ask.reply == ASK_WHICH_ITEM
    done = svc.handle(session_id="s3", text="A품목")
    assert done.lines[0]["qty"] == 15
    assert done.total == 7_500_000


def test_amount_conflict_asks_then_calc_wins() -> None:
    svc = _svc()
    out = svc.handle(session_id="s4", text="A품목 15개 단가 500원 금액 10000원")
    assert "다시 확인 하겠습니다" in out.reply
    assert "총 7,500원이 맞습니까?" in out.reply
    assert out.lines[0]["amount_calc"] == 7500
    yes = svc.handle(session_id="s4", text="네")
    assert yes.lines[0]["amount_conflict"] is False
    assert yes.total == 7500


def test_image_fail_three_reasons() -> None:
    empty = _svc(vision=lambda _b: "")
    assert empty.handle(session_id="i1", image_base64="YQ==", filename="a.png", mime="image/png").reply == UNREAD_NO_TEXT

    fields = _svc(vision=lambda _b: "상호만 있음")
    assert fields.handle(session_id="i2", image_base64="YQ==", filename="a.png", mime="image/png").reply == UNREAD_NO_FIELDS

    def boom(_b: bytes) -> str:
        raise RuntimeError("down")

    vis = _svc(vision=boom)
    assert vis.handle(session_id="i3", image_base64="YQ==", filename="a.png", mime="image/png").reply == UNREAD_VISION


def test_excel_rejected() -> None:
    svc = _svc()
    out = svc.handle(session_id="f1", filename="list.xlsx", mime="application/vnd.ms-excel")
    assert out.reply == IMAGE_ONLY


def test_two_images_merge() -> None:
    texts = iter(["A품목 1개 단가 100원", "B상품 2개 단가 200원"])
    svc = _svc(vision=lambda _b: next(texts))
    svc.handle(session_id="m1", image_base64="YQ==", filename="1.png", mime="image/png")
    out = svc.handle(session_id="m1", image_base64="YQ==", filename="2.png", mime="image/png")
    assert len(out.lines) == 2
    assert out.total == 500


def test_clear_wipes_lines() -> None:
    svc = _svc()
    svc.handle(session_id="c1", text="A품목 10개 단가 500000원")
    cleared = svc.clear("c1")
    assert cleared.lines == []
    again = svc.handle(session_id="c1", text="안녕하세요")
    assert again.lines == []


def test_missing_price_then_fill() -> None:
    svc = _svc()
    asked = svc.handle(session_id="p1", text="A품목 10개")
    assert "단가" in asked.reply
    filled = svc.handle(session_id="p1", text="500000원")
    assert filled.total == 5_000_000
    assert filled.kinds_selectable is True


def test_select_kind_enables_preview() -> None:
    svc = _svc()
    svc.handle(session_id="k1", text="A품목 10개 단가 500000원")
    selected = svc.handle(session_id="k1", action="select_kind", kind_id="receipt")
    assert selected.preview_ready is True
    preview = svc.handle(session_id="k1", action="preview")
    assert "save" in preview.action_enabled
    assert "download" in preview.action_enabled
    assert "send" not in preview.action_enabled


def test_hapgye_mismatch_asks_calc() -> None:
    svc = _svc()
    out = svc.handle(session_id="h1", text="B상품 10개 단가 20000원 합계 300000원")
    assert "다시 확인 하겠습니다" in out.reply
    assert "총 200,000원이 맞습니까?" in out.reply
    assert out.lines[0]["amount_calc"] == 200000
    yes = svc.handle(session_id="h1", text="네")
    assert yes.lines[0]["amount_conflict"] is False
    assert yes.total == 200000


def test_amount_only_guide_not_chitchat_reset() -> None:
    from app.tools.ocr_receipt import AMOUNT_ONLY_GUIDE

    svc = _svc()
    svc.handle(session_id="a1", text="A품목 10개 단가 500000원")
    out = svc.handle(session_id="a1", text="A품목 금액은 10000원이야")
    assert out.reply == AMOUNT_ONLY_GUIDE
    assert len(out.lines) == 1


def test_same_name_price_conflict_ask_then_pick() -> None:
    texts = iter(
        ["카트리지 1개 단가 1000원", "카트리지 1개 단가 2000원"]
    )
    svc = _svc(vision=lambda _b: next(texts))
    svc.handle(session_id="c2", image_base64="YQ==", filename="1.png", mime="image/png")
    ask = svc.handle(session_id="c2", image_base64="YQ==", filename="2.png", mime="image/png")
    assert "다르게 읽혔" in ask.reply
    assert len(ask.lines) == 1
    picked = svc.handle(session_id="c2", text="2000원")
    assert picked.lines[0]["unit_price"] == 2000
    assert picked.total == 2000


def test_unclear_lines_kept_and_confirm() -> None:
    raw = (
        "A4용지 개당 25,000원 2box 총 50,000원\n"
        "사무용 의자 1개 150,000원"
    )
    svc = _svc(vision=lambda _b: raw)
    out = svc.handle(session_id="u1", image_base64="YQ==", filename="1.png", mime="image/png")
    assert out.raw_text
    assert "A4용지" in (out.reply + str(out.unclear_lines))
    assert any(row["name"] == "사무용 의자" for row in out.lines)
    # 미매칭이 있으면 바로 되물음 — 「읽었어요」만으로 끝내지 않음
    assert "입니까" in out.reply or "확정하지" in out.reply
    yes = svc.handle(session_id="u1", text="네")
    names = {row["name"] for row in yes.lines}
    assert "A4용지" in names
    assert yes.unclear_lines == [] or len(yes.unclear_lines) < len(out.unclear_lines or [])


def test_unclear_line_reply_with_explanation_does_not_create_bogus_item() -> None:
    """되물음에 '2box는 2개야'처럼 설명을 덧붙이면, 엉뚱한 '2box는' 품목을 새로 만들면 안 되고
    원래 제안(A4용지)의 수량만 보정해서 반영해야 한다."""
    raw = "A4용지 개당 25,000원 2box 총 50,000원"
    svc = _svc(vision=lambda _b: raw)
    out = svc.handle(session_id="u2", image_base64="YQ==", filename="1.png", mime="image/png")
    assert any(u["raw"] and "A4용지" in u["raw"] for u in (out.unclear_lines or []))

    replied = svc.handle(session_id="u2", text="2box는 2개야")
    names = {row["name"] for row in replied.lines}
    assert "2box는" not in names
    assert "A4용지" in names
    a4 = next(row for row in replied.lines if row["name"] == "A4용지")
    assert a4["qty"] == 2
    assert a4["unit_price"] == 25000


def test_bare_word_asks_to_confirm_item_then_fills_missing_fields() -> None:
    """숫자 없이 단어 하나만 치면 잡담으로 버리지 말고 품목인지 되물어야 한다."""
    svc = _svc()
    asked = svc.handle(session_id="n1", text="카트리지")
    assert asked.reply == "카트리지가 품목입니까?"
    assert asked.lines == []

    confirmed = svc.handle(session_id="n1", text="네")
    assert confirmed.reply == "수량, 개당단가, 총금액을 입력하세요."
    assert confirmed.lines[0]["name"] == "카트리지"

    filled = svc.handle(session_id="n1", text="5개 3000원")
    assert filled.lines[0]["qty"] == 5
    assert filled.lines[0]["unit_price"] == 3000
    assert filled.total == 15000


def test_bare_word_confirm_with_qty_price_in_same_reply() -> None:
    svc = _svc()
    svc.handle(session_id="n2", text="카트리지")
    out = svc.handle(session_id="n2", text="응, 5개 3000원")
    assert out.lines[0]["qty"] == 5
    assert out.lines[0]["unit_price"] == 3000


def test_bare_word_reject_confirm_gives_generic_guide() -> None:
    svc = _svc()
    svc.handle(session_id="n3", text="카트리지")
    out = svc.handle(session_id="n3", text="아니야")
    assert out.reply == ASK_ITEM_FIELDS
    assert out.lines == []


def test_ambiguous_sentence_gets_generic_guide_not_bare_word_confirm() -> None:
    svc = _svc()
    out = svc.handle(session_id="n4", text="이거 뭐라고 써야 하는지 모르겠다")
    assert out.reply == ASK_ITEM_FIELDS


def test_greeting_is_not_treated_as_item_word() -> None:
    svc = _svc()
    out = svc.handle(session_id="n5", text="안녕")
    assert out.reply == CHITCHAT_GUIDE
    assert out.lines == []


def test_unit_word_order_confirmed_directly_not_asked() -> None:
    """"10박스 개당 25,000원"처럼 수량단위가 가격보다 먼저 나와도 되묻지 않고 바로 확정돼야 한다."""
    raw = "거치대 5개 12,000원\nA4용지 10박스 개당 25,000원"
    svc = _svc(vision=lambda _b: raw)
    out = svc.handle(session_id="n6", image_base64="YQ==", filename="1.png", mime="image/png")
    names = {row["name"] for row in out.lines}
    assert "A4용지" in names
    a4 = next(row for row in out.lines if row["name"] == "A4용지")
    assert a4["qty"] == 10
    assert a4["unit_price"] == 25000
    assert out.unclear_lines == []


def test_unit_word_price_label_confirms_without_asking() -> None:
    """"3잔 잔당 4500원"처럼 확실한 문장은 되묻지 말고 바로 확정해야 한다."""
    svc = _svc()
    out = svc.handle(session_id="n8", text="아메리카노 3잔 잔당 4500원")
    names = {row["name"] for row in out.lines}
    assert "아메리카노" in names
    item = next(row for row in out.lines if row["name"] == "아메리카노")
    assert item["qty"] == 3
    assert item["unit_price"] == 4500
    assert out.unclear_lines == []


def test_unclear_reply_no_longer_stuck_forever_when_no_initial_suggestion() -> None:
    """제안을 처음에 못 만들었어도, 재답변에서 수량·단가가 뽑히면 그대로 버려지지 않고 반영돼야 한다."""
    raw = "거치대 5개 12,000원\n미확인품목 999"
    svc = _svc(vision=lambda _b: raw)
    first = svc.handle(session_id="n7", image_base64="YQ==", filename="1.png", mime="image/png")
    assert first.unclear_lines and first.unclear_lines[0]["suggestion"] is None

    replied = svc.handle(session_id="n7", text="5개 3000원")
    assert any(row["name"] == "미확인품목" for row in replied.lines)
    item = next(row for row in replied.lines if row["name"] == "미확인품목")
    assert item["qty"] == 5
    assert item["unit_price"] == 3000
