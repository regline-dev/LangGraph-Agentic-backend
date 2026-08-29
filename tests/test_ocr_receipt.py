"""OCR 영수증 Tool 단위 테스트."""

from app.tools.ocr_receipt import (
    AMOUNT_ONLY_GUIDE,
    ASK_WHICH_ITEM,
    UNREAD_NO_FIELDS,
    UNREAD_NO_TEXT,
    UNREAD_VISION,
    apply_natural_edit,
    classify_intent,
    completeness,
    extract_doc_total_ocr,
    guess_item_name,
    image_fail_reason,
    is_amount_only_mention,
    merge_line_lists,
    parse_lines_from_text,
    totals,
)


def test_tool1_parses_qty_and_won() -> None:
    lines = parse_lines_from_text("A품목 10개 단가 500000원")
    assert len(lines) == 1
    assert lines[0].name == "A품목"
    assert lines[0].qty == 10
    assert lines[0].unit_price == 500000
    assert lines[0].amount_calc == 5_000_000
    assert lines[0].line_id


def test_tool1_amount_conflict_is_not_final() -> None:
    lines = parse_lines_from_text("A품목 10개 단가 500원 금액 10000원")
    assert lines[0].amount_conflict is True
    assert lines[0].amount_calc == 5000
    ok, msg = completeness(lines)
    assert ok is False
    assert msg == (
        "A품목 단가나 수량을 다시 확인 하겠습니다.\n"
        "수량 10개, 개당 500원으로 총 5,000원이 맞습니까?"
    )


def test_tool1_hapgye_on_line_is_amount_ocr() -> None:
    lines = parse_lines_from_text("B상품 10개 단가 20000원 합계 300000원")
    assert len(lines) == 1
    assert lines[0].amount_ocr == 300000
    assert lines[0].amount_calc == 200000
    assert lines[0].amount_conflict is True
    ok, msg = completeness(lines)
    assert ok is False
    assert "200,000" in (msg or "")


def test_doc_total_outside_item_line() -> None:
    raw = "A품목 1개 단가 100원\n합계 999원"
    lines = parse_lines_from_text(raw)
    assert lines[0].amount_calc == 100
    assert extract_doc_total_ocr(raw) == 999
    ok, msg = completeness(lines, doc_total_ocr=999)
    assert ok is False
    assert "계산 합계" in (msg or "")


def test_doc_total_inside_item_line_not_doc_level() -> None:
    raw = "B상품 10개 단가 20000원 합계 300000원"
    assert extract_doc_total_ocr(raw) is None


def test_image_fail_reasons() -> None:
    assert image_fail_reason(vision_error=True, ocr_text="x", lines=[]) == UNREAD_VISION
    assert image_fail_reason(vision_error=False, ocr_text="", lines=[]) == UNREAD_NO_TEXT
    assert (
        image_fail_reason(vision_error=False, ocr_text="상호만", lines=[])
        == UNREAD_NO_FIELDS
    )


def test_chitchat_skips_tool1() -> None:
    assert classify_intent("안녕하세요", has_lines=False) == "chitchat"


def test_typed_items_are_data() -> None:
    text = "A품목 10개 단가 500000원"
    assert classify_intent(text, has_lines=False) == "data"


def test_amount_only_intent() -> None:
    assert classify_intent("A품목 금액은 10000원이야", has_lines=True) == "amount_only"
    assert AMOUNT_ONLY_GUIDE


def test_amount_word_with_edit_is_not_amount_only() -> None:
    """「금액」이 섞여 있어도 수정 요청이면 amount_only가 가로채지 않는다."""
    for text in ("금액 삭제해줘", "금액 빼줘", "금액 수정해줘"):
        assert is_amount_only_mention(text) is False
        assert classify_intent(text, has_lines=True) == "edit"


def test_edit_intent_without_quantity() -> None:
    """분류(edit인가)는 수량 유무와 무관하다. 처리 가능 여부는 Tool #3가 따로 본다."""
    assert classify_intent("삭제해줘", has_lines=True) == "edit"
    assert classify_intent("커피 빼줘", has_lines=True) == "edit"
    assert classify_intent("단가 바꿔", has_lines=True) == "edit"


def test_tool2_missing_unit_price() -> None:
    lines = parse_lines_from_text("A품목 10개")
    ok, msg = completeness(lines)
    assert ok is False
    assert "단가" in (msg or "")


def test_tool2_complete_when_three_fields() -> None:
    lines = parse_lines_from_text("A품목 10개 단가 500000원")
    ok, _ = completeness(lines)
    assert ok is True
    assert totals(lines) == 5_000_000


def test_tool3_asks_item_when_missing() -> None:
    lines = parse_lines_from_text("A품목 10개 단가 500000원")
    _, msg = apply_natural_edit("수량 15개로 고쳐줘", lines)
    assert msg == ASK_WHICH_ITEM


def test_tool3_updates_named_item() -> None:
    lines = parse_lines_from_text("A품목 10개 단가 500000원")
    lines, msg = apply_natural_edit("A품목 수량 15개", lines)
    assert "15개" in msg
    assert lines[0].qty == 15
    assert lines[0].amount_calc == 7_500_000
    ok, _ = completeness(lines)
    assert ok is True


def test_merge_two_images_one_receipt() -> None:
    a = parse_lines_from_text("A품목 1개 단가 100원")
    b = parse_lines_from_text("B상품 2개 단가 200원")
    merged, conflicts = merge_line_lists(a, b)
    assert conflicts == []
    assert len(merged) == 2
    assert totals(merged) == 500


def test_merge_same_name_fills_from_one_side() -> None:
    a = parse_lines_from_text("카트리지 2개")
    b = parse_lines_from_text("카트리지 2개 단가 5000원")
    merged, conflicts = merge_line_lists(a, b)
    assert conflicts == []
    assert len(merged) == 1
    assert merged[0].unit_price == 5000
    assert merged[0].amount_calc == 10000


def test_merge_same_name_both_missing_price_stays_unclear() -> None:
    """3-4b: 같은 품명, 둘 다 단가가 비면 충돌 없이 None으로 남아 미확정 상태가 된다."""
    a = parse_lines_from_text("카트리지 2개")
    b = parse_lines_from_text("카트리지 2개")
    merged, conflicts = merge_line_lists(a, b)
    assert conflicts == []
    assert len(merged) == 1
    assert merged[0].qty == 2
    assert merged[0].unit_price is None
    ok, msg = completeness(merged)
    assert ok is False
    assert "단가" in (msg or "")


def test_merge_same_name_price_conflict() -> None:
    a = parse_lines_from_text("카트리지 1개 단가 1000원")
    b = parse_lines_from_text("카트리지 1개 단가 2000원")
    merged, conflicts = merge_line_lists(a, b)
    assert len(merged) == 1
    assert len(conflicts) == 1
    assert conflicts[0].field == "unit_price"
    assert set(conflicts[0].options) == {1000, 2000}
    assert merged[0].unit_price is None


RECEIPT01_RAW = """A4용지 개당 25,000원 2box 총 50,000원
프린터 토너 카트리지 1개 89,000원
사무용 의자 1개 150,000원
노트북 거치대 5개, 단가 12,000원
아메리카노 3잔, 잔당 4,500원"""


def test_receipt01_no_silent_drop() -> None:
    from app.tools.ocr_receipt import parse_raw_with_unclear

    confirmed, unclear = parse_raw_with_unclear(RECEIPT01_RAW)
    names = {item.name for item in confirmed}
    unclear_raw = "\n".join(u.raw for u in unclear)
    # 거치대·아메리카노는 단위 목록 확장으로 이제 바로 확정,
    # A4용지는(가격이 수량보다 먼저 나오는 순서라) 여전히 되물음 큐
    # 품목명은 숫자 앞 단어 전부(안 잘림)
    assert "노트북 거치대" in names
    assert "프린터 토너 카트리지" in names or "사무용 의자" in names
    assert "아메리카노" in names
    assert "A4용지" in unclear_raw
    assert any(u.suggestion and u.suggestion.qty == 2 for u in unclear)


def test_comma_before_unit_price_parses() -> None:
    lines = parse_lines_from_text("노트북 거치대 5개, 단가 12,000원")
    assert len(lines) == 1
    assert lines[0].qty == 5
    assert lines[0].unit_price == 12000


def test_multi_word_item_name_not_truncated() -> None:
    """품목명이 여러 단어면(예: "노트북 거치대") 숫자 앞 단어 전부가 이름이어야 한다."""
    lines = parse_lines_from_text("노트북 거치대 5개, 단가 12,000원")
    assert lines[0].name == "노트북 거치대"

    lines2 = parse_lines_from_text("프린터 토너 카트리지 1개 89,000원")
    assert lines2[0].name == "프린터 토너 카트리지"


def test_item_name_keeps_colon_hyphen_and_following_token() -> None:
    """품목명 글자에 콜론·하이픈이 있으면 숫자 앞까지 이름을 자르지 않는다."""
    lines = parse_lines_from_text("ID: abjhalbbkk 10개 단가 1000원")
    assert len(lines) == 1
    assert lines[0].name == "ID: abjhalbbkk"

    lines2 = parse_lines_from_text("SKU-99 2개 단가 500원")
    assert lines2[0].name == "SKU-99"


def test_guess_item_name_keeps_phrase_until_qty() -> None:
    """첫 공백 토큰만 쓰지 않고, 수량·단가 앞까지를 품목명으로 본다."""
    assert guess_item_name("ID: abjhalbbkk") == "ID: abjhalbbkk"
    assert guess_item_name("노트북 거치대 5개") == "노트북 거치대"


def test_suggest_item_handles_unit_word_before_price_korean() -> None:
    """"수량단위 → 가격" 순서, 한글 단위("박스")도 이제 되묻지 않고 바로 확정돼야 한다."""
    from app.tools.ocr_receipt import parse_raw_with_unclear

    confirmed, unclear = parse_raw_with_unclear("A4용지 10박스 개당 25,000원")
    assert unclear == []
    assert len(confirmed) == 1
    item = confirmed[0]
    assert item.name == "A4용지"
    assert item.qty == 10
    assert item.unit_price == 25000


def test_suggest_item_no_hardcoded_unit_still_asks_something() -> None:
    """단위 목록에 없는 표현이라도, 이름조차 못 뽑는 게 아니면 되물어야 한다(제안 없어도 무한반복 금지)."""
    from app.tools.ocr_receipt import parse_raw_with_unclear

    confirmed, unclear = parse_raw_with_unclear("미확인품목 999")
    assert confirmed == []
    assert len(unclear) == 1
    assert unclear[0].suggestion is None
    assert "확정하지" in unclear[0].ask_message


def test_newly_completed_items_only_this_turn() -> None:
    from app.tools.ocr_receipt import LineItem, newly_completed_items

    before = [LineItem(name="커피", qty=2, unit_price=3000)]
    after = [
        LineItem(name="커피", qty=2, unit_price=3000),
        LineItem(name="율무차", qty=2, unit_price=4000),
    ]
    filled = newly_completed_items(before, after)
    assert [item.name for item in filled] == ["율무차"]


def test_format_just_filled_preview_reply() -> None:
    from app.tools.ocr_receipt import KIND_READY, LineItem, format_just_filled_preview_reply

    item = LineItem(name="율무차", qty=2, unit_price=4000)
    item.recompute()
    assert format_just_filled_preview_reply([item], kind_selected=True) == (
        "율무차, 2개, 단가 4,000원, 총 8,000원 입니다.\n"
        "내용을 확인하세요.\n"
        "미리보기를 눌러주세요"
    )
    assert format_just_filled_preview_reply([item], kind_selected=False).endswith(KIND_READY)


def test_format_just_filled_preview_reply_uses_qty_unit() -> None:
    from app.tools.ocr_receipt import LineItem, format_just_filled_preview_reply

    item = LineItem(name="율무차", qty=2, unit_price=4000, qty_unit="잔")
    item.recompute()
    assert format_just_filled_preview_reply([item], kind_selected=True) == (
        "율무차, 2잔, 단가 4,000원, 총 8,000원 입니다.\n"
        "내용을 확인하세요.\n"
        "미리보기를 눌러주세요"
    )


def test_name_confirm_messages_use_name_template() -> None:
    from app.tools.ocr_receipt import name_confirm_ask_message, name_confirm_cancel_message

    assert name_confirm_ask_message("율무차") == (
        "율무차가 품목이 맞다면 (수량, 단가)를 알려주세요."
    )
    assert name_confirm_cancel_message("율무차") == (
        "품목 율무차는 취소되었습니다.\n"
        "품목·수량·단가를 이어서 입력하시거나\n"
        "미리보기를 눌러주세요"
    )


def test_extract_qty_unit_from_cup() -> None:
    from app.tools.ocr_receipt import extract_qty_unit

    assert extract_qty_unit("2잔 4000원") == "잔"
    assert extract_qty_unit("2개 4000원") == "개"


def test_extract_qty_general_bare_leading_number_with_price() -> None:
    """단위 없는 앞숫자 + 원 금액 → 수량은 앞숫자, 단가는 원 금액."""
    from app.tools.ocr_receipt import extract_price_from_text, extract_qty_general

    assert extract_qty_general("2 3000원") == 2
    assert extract_price_from_text("2 3000원") == 3000
    assert extract_qty_general("3000원") is None
    assert extract_price_from_text("3000원") == 3000
    assert extract_qty_general("2개 2000원") == 2


def test_check_completeness_missing_qty_is_fillable() -> None:
    from app.tools.ocr_receipt import ASK_MISSING_PRICE, ASK_MISSING_QTY, LineItem, check_completeness

    qty_missing = check_completeness([LineItem(name="율무차", qty=None, unit_price=3000)])
    assert qty_missing.ok is False
    assert qty_missing.pending_kind == "fill_name"
    assert qty_missing.pending_name == "율무차"
    assert qty_missing.message == ASK_MISSING_QTY.format(name="율무차")
    assert "단가" not in (qty_missing.message or "")

    price_missing = check_completeness([LineItem(name="커피", qty=2, unit_price=None)])
    assert price_missing.pending_kind == "fill_name"
    assert price_missing.message == ASK_MISSING_PRICE.format(name="커피")


def test_apply_fill_overwrites_stale_qty_and_price_from_full_answer() -> None:
    """재개 답에 수량·단가가 있으면 스테일 값을 덮어쓴다. 답에 없는 필드는 유지."""
    from app.tools.ocr_receipt import LineItem, apply_fill

    stale = [LineItem(name="율무차", qty=None, unit_price=3000)]
    apply_fill("2개 2000원", stale, "율무차")
    assert stale[0].qty == 2
    assert stale[0].unit_price == 2000
    assert stale[0].qty_unit == "개"

    qty_only = [LineItem(name="율무차", qty=None, unit_price=3000)]
    apply_fill("2개", qty_only, "율무차")
    assert qty_only[0].qty == 2
    assert qty_only[0].unit_price == 3000
