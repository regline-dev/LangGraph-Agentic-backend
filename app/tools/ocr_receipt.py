"""OCR 영수증 Tool #1·#2·#3 — 단위 텍스트 규칙. LLM 없음."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Intent = Literal["chitchat", "data", "edit", "fill", "amount_only"]

# 되물음 종류. 답변이 다음 턴에 어느 Tool로 들어가야 하는지를 이 값으로 정한다.
PendingKind = Literal[
    "conflict",
    "fill_name",
    "unclear",
    "field_conflict",
    "name_confirm",
    "ask_item",
    "add_confirm",
]

UNREAD_NO_TEXT = (
    "못 읽었습니다. 사진에서 글자를 찾지 못했습니다. 더 가까이, 밝게 찍어 주세요."
)
UNREAD_NO_FIELDS = (
    "못 읽었습니다. 글자는 있으나 품목·수량·단가로 읽지 못했습니다."
)
UNREAD_VISION = "지금은 사진을 읽지 못했습니다. 잠시 후 다시 올려 주세요."
CHITCHAT_GUIDE = (
    "영수증에 넣을 품목·수량·단가를 채팅으로 적거나, 사진을 올려 주세요."
)
ASK_ITEM_FIELDS = (
    "견적서, 거래명세서, 영수증, 청구서 작성을 도와드립니다.\n"
    "품목, 수량, 개당단가를 입력하세요"
)
ASK_QTY_PRICE_AMOUNT = "수량, 개당단가, 총금액을 입력하세요."
ASK_MISSING_QTY = "{name}의 수량을 확인할 수 없어요. 몇 개인가요?"
ASK_MISSING_PRICE = "{name}의 단가를 확인할 수 없어요. 얼마인가요?"
_GREETING = re.compile(r"(안녕|하이|헬로|고마워|감사|반가워|수고)")
AMOUNT_ONLY_GUIDE = (
    "금액은 수량×단가로 자동 계산됩니다. 수량이나 단가를 알려주세요."
)
ASK_WHICH_ITEM = "어떤 품목의 수량을 고칠까요?"
IMAGE_ONLY = "이미지만 지원합니다"
READ_OK_PREFIX = "읽었어요! 아래 내용을 확인해주세요"
KIND_READY = "문서 종류를 선택한 뒤 미리보기를 눌러 주세요."
AFFIRM = re.compile(r"(네|예|응|맞|확인|좋아요|그래|계산)")
# 되물음 부정 답(추가할까요? 아니오). 품목 표현이 늘어날 때마다 키워드를 더하는 목록이 아님.
_DENY = re.compile(r"(아니|싫|말고|취소)")
EDIT_UNSUPPORTED_GUIDE = "삭제는 아직 지원하지 않습니다, 수량만 조정 가능합니다"
ADD_CONFIRM_TEMPLATE = "품목 {n}개를 추가할까요?"
PREVIEW_PLEASE = "미리보기를 눌러주세요"


def name_confirm_ask_message(name: str) -> str:
    """단어 하나 품목 후보 확인. 다음 답은 수량·단가 또는 부정."""
    return f"{name}가 품목이 맞다면 (수량, 단가)를 알려주세요."


def _topic_particle(word: str) -> str:
    """한글 마지막 글자 받침 있으면 은, 없으면 는."""
    if not word:
        return "는"
    code = ord(word[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return "은" if (code - 0xAC00) % 28 else "는"
    return "는"


def name_confirm_cancel_message(name: str) -> str:
    """name_confirm 부정 — 후보만 취소. 기존 확정 목록은 유지."""
    return (
        f"품목 {name}{_topic_particle(name)} 취소되었습니다.\n"
        "품목·수량·단가를 이어서 입력하시거나\n"
        f"{PREVIEW_PLEASE}"
    )

# 6-2a 추가/수정 판별용 수정 의도 키워드. 새 표현은 목록에만 더한다.
_EDIT_KEYWORDS = ["고쳐", "수정", "바꿔", "변경", "삭제", "빼", "지워", "치워"]
_EDIT = re.compile("|".join(re.escape(word) for word in _EDIT_KEYWORDS))

# 위 중에서 1차 구현 범위(수량 조정) 밖인 것 — Tool #3가 안내만 하고 끝낸다.
_EDIT_UNSUPPORTED_KEYWORDS = ["삭제", "빼", "지워", "치워", "단가", "가격"]
_EDIT_UNSUPPORTED = re.compile(
    "|".join(re.escape(word) for word in _EDIT_UNSUPPORTED_KEYWORDS)
)

# 수량 단위 표현 — 확정 파서(_LINE 등)와 되물음 제안(_SUGGEST_QTY) 양쪽에서 같이 쓴다
_QTY_UNIT_WORDS_KO = [
    "개", "벌", "켤레", "상자", "박스", "병", "캔", "팩", "통", "잔",
    "봉지", "조각", "덩어리", "송이", "다발", "그루", "마리", "명", "분", "권",
    "장", "정", "자루", "방울", "톨", "알", "첩", "롤", "판", "포기",
    "대", "채", "접", "축", "두름", "제", "도막", "드럼", "말", "되", "홉",
]
_QTY_UNIT_WORDS_EN = [
    "piece", "suit", "pair", "box", "bottle", "can", "carton", "tub", "cup", "glass",
    "bag", "slice", "chunk", "loaf", "lump", "bunch", "head", "sheet", "tablet", "pill",
    "stick", "drop", "grain", "packet", "roll", "tray", "bar", "scoop", "spoonful", "pack",
    "pile", "jar", "jug", "mug", "bowl", "plate", "sack", "crate", "cylinder", "unit", "set",
]
_QTY_UNIT_PATTERN = "|".join(
    re.escape(w)
    for w in sorted(_QTY_UNIT_WORDS_KO + _QTY_UNIT_WORDS_EN, key=len, reverse=True)
)
_QTY_UNIT_ALT = rf"(?:개|EA|ea|{_QTY_UNIT_PATTERN})"

# 품목명은 숫자(수량) 나오기 전까지 이어지는 단어 전부.
# 콜론·하이픈 등은 코드/SKU형 이름에 쓰이므로 글자 집합에 포함한다(특정 품목명 분기는 없음).
_NAME_TOKEN = r"[가-힣A-Za-z0-9:_：._-]+"
_NAME_WORDS = rf"{_NAME_TOKEN}(?:\s+{_NAME_TOKEN})*?"

_LINE = re.compile(
    rf"(?P<name>{_NAME_WORDS})\s+"
    rf"(?P<qty>\d+)\s*{_QTY_UNIT_ALT}\s*,?\s*"  # 수량 뒤 쉼표 허용 (거치대 5개, 단가 …)
    rf"(?:단가\s*|{_QTY_UNIT_ALT}당\s*)?(?P<price>[\d,]+)\s*원"
    # 같은 줄의 금액·합계만 품목 검산용 (줄바꿈 뒤 문서 합계는 제외)
    r"(?:[ \t]+(?:(?:금액|합계)\s*)?(?P<amount>[\d,]+)\s*원)?",
    re.IGNORECASE,
)
_QTY_ONLY = re.compile(
    rf"(?:(?P<name>{_NAME_WORDS})\s+)?(?:수량\s*)?(?P<qty>\d+)\s*{_QTY_UNIT_ALT}",
    re.IGNORECASE,
)
_NAMED_QTY = re.compile(
    rf"(?P<name>{_NAME_WORDS})\s+(?P<qty>\d+)\s*{_QTY_UNIT_ALT}\s*,?",
    re.IGNORECASE,
)
_SUGGEST_QTY = re.compile(
    rf"(?P<qty>\d+)\s*(?P<qty_unit>{_QTY_UNIT_PATTERN})",
    re.IGNORECASE,
)
# 단위 없는 앞숫자. "2 3000원"·"2"는 수량. "3000원"은 단가라 제외(숫자와 원 사이 공백 없음).
_BARE_LEADING_QTY = re.compile(r"^\s*(?P<qty>\d+)(?:\s+|$)")
_DOC_TOTAL_LINE = re.compile(
    r"^\s*(?:총\s*공급대가|합계)\s*[:：]?\s*[\d,]+\s*원\s*$"
)
_HAS_DIGIT = re.compile(r"\d")
_PRICE_ONLY = re.compile(r"(?P<price>[\d,]+)\s*원")
_DOC_TOTAL = re.compile(
    r"(?:총\s*공급대가|합계)\s*[:：]?\s*([\d,]+)\s*원"
)
_AMOUNT_MENTION = re.compile(r"금액")


def _to_int(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    if not digits:
        return None
    return int(digits)


def _new_line_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class LineItem:
    name: str
    qty: int | None = None
    unit_price: int | None = None
    amount_ocr: int | None = None
    amount_calc: int | None = None
    amount_conflict: bool = False
    qty_unit: str | None = None  # 입력에서 읽은 단위. 없으면 안내문에만 '개'
    line_id: str = field(default_factory=_new_line_id)

    def recompute(self) -> None:
        if self.qty is not None and self.unit_price is not None:
            self.amount_calc = self.qty * self.unit_price
            self.amount_conflict = (
                self.amount_ocr is not None and self.amount_ocr != self.amount_calc
            )
        else:
            self.amount_calc = None
            self.amount_conflict = False


@dataclass
class FieldConflict:
    """같은 품명 병합 시 양쪽 값이 다를 때."""

    name: str
    field: str  # qty | unit_price
    options: list[int]


@dataclass
class UnclearLine:
    """정규식이 확정 못 한 원문 줄 — 버리지 않고 되물음."""

    raw: str
    suggestion: LineItem | None = None
    ask_message: str = ""


def _line_fully_matched(line: str) -> list[LineItem]:
    """한 줄에서 확정 파싱(수량 단위 개/EA + 단가 원)."""
    return parse_lines_from_text(line)


def _split_into_segments(raw: str) -> list[str]:
    """
    처리 단위로 나눈다. 실제 개행이 있으면 줄 단위 그대로.
    개행이 없으면(입력창이 한 줄이라 줄바꿈이 사라진 경우) 확정 패턴(_LINE)의
    경계로 끊어서, 매칭 안 되는 구간이 옆 품목에 묻혀 조용히 사라지지 않게 한다.
    """
    text = raw or ""
    if "\n" in text:
        return text.splitlines()
    points = {0, len(text)}
    for match in _LINE.finditer(text):
        points.add(match.start())
        points.add(match.end())
    ordered = sorted(points)
    segments = [text[ordered[i] : ordered[i + 1]] for i in range(len(ordered) - 1)]
    return [s for s in segments if s.strip()]


def suggest_item(line: str) -> LineItem | None:
    """미매칭 줄에 대한 해석 제안.
    특정 단위 단어의 순서에 의존하지 않고, 이름은 첫 토큰으로,
    단가는 '~원' 숫자로, 수량은 단위 표현이 붙은 숫자로 일반적으로 추정한다.
    나온 것만 채우고(부분 제안 허용), 이름조차 못 뽑으면 None."""
    cleaned = (line or "").strip()
    if not cleaned:
        return None
    name = guess_item_name(cleaned)
    if not name or name[0].isdigit():
        return None

    qty_match = _SUGGEST_QTY.search(cleaned)
    qty = _to_int(qty_match.group("qty")) if qty_match else None

    prices = [_to_int(m.group("price")) for m in _PRICE_ONLY.finditer(cleaned)]
    price = prices[0] if prices else None
    amount_ocr = prices[1] if len(prices) > 1 else None

    if qty is None and price is None:
        return None

    item = LineItem(name=name, qty=qty, unit_price=price, amount_ocr=amount_ocr)
    item.recompute()
    return item


def unclear_ask_message(raw: str, suggestion: LineItem | None) -> str:
    if suggestion is None or (suggestion.qty is None and suggestion.unit_price is None):
        return (
            "이 줄을 품목·수량·단가로 확정하지 못했어요.\n"
            f"「{raw}」\n"
            "예: 품목명 N개 단가 N원 형식으로 알려 주세요."
        )
    sug = suggestion
    lines = [f"질문 「{raw}」"]
    if sug.qty is not None:
        lines.append(f"1. {sug.name} 수량이 {sug.qty}개입니까?")
    else:
        lines.append(f"1. {sug.name} 수량이 몇 개입니까?")
    if sug.unit_price is not None:
        price_line = f"2. 개당 가격이 {sug.unit_price:,}원입니까?"
    else:
        price_line = "2. 개당 가격이 얼마입니까?"
    calc = sug.amount_calc
    # 총액과 계산이 일치할 때는 질문이 길어져 안 읽히니 "(총 N원)"만 짧게 붙인다.
    # 불일치일 때만 사용자가 놓치면 안 되는 정보라서 별도 줄로 경고한다.
    if calc is not None:
        price_line += f" (총 {calc:,}원)"
    lines.append(price_line)
    if calc is not None and sug.amount_ocr is not None and sug.amount_ocr != calc:
        lines.append(f"(적어주신 총액은 {sug.amount_ocr:,}원인데 계산은 {calc:,}원이에요)")
    return "\n".join(lines)


def parse_raw_with_unclear(raw: str) -> tuple[list[LineItem], list[UnclearLine]]:
    """
    원문을 줄 단위로 나눠 확정 품목 / 미매칭(되물음)으로 분류.
    미매칭은 버리지 않는다.
    """
    confirmed: list[LineItem] = []
    unclear: list[UnclearLine] = []
    for line in _split_into_segments(raw):
        cleaned = line.strip()
        if not cleaned:
            continue
        if _DOC_TOTAL_LINE.match(cleaned):
            continue
        items = _line_fully_matched(cleaned)
        # 줄 전체가 확정 패턴으로 설명되면 통과
        if items and _LINE.search(cleaned):
            confirmed.extend(items)
            continue
        if items and not _LINE.search(cleaned):
            # 수량만(_NAMED_QTY) — 단가 없는 줄은 확정에 넣되 단가 되물음으로 이어짐
            # 단, 원문에 가격 힌트가 있으면 조용한 단가 소실이므로 unclear
            if re.search(r"[\d,]+\s*원|단가", cleaned):
                sug = items[0]
                # 단가가 비어 있으면 unclear로 올려 제안/되물음
                if sug.unit_price is None:
                    better = suggest_item(cleaned)
                    suggestion = better or sug
                    unclear.append(
                        UnclearLine(
                            raw=cleaned,
                            suggestion=suggestion if suggestion.unit_price else sug,
                            ask_message=unclear_ask_message(
                                cleaned,
                                suggestion if suggestion and suggestion.unit_price else None,
                            ),
                        )
                    )
                    continue
            confirmed.extend(items)
            continue
        if not _HAS_DIGIT.search(cleaned):
            continue
        # 숫자 있는 미매칭 줄 → 버리지 않음
        suggestion = suggest_item(cleaned)
        unclear.append(
            UnclearLine(
                raw=cleaned,
                suggestion=suggestion,
                ask_message=unclear_ask_message(cleaned, suggestion),
            )
        )
    return confirmed, unclear


def unclear_as_dicts(rows: list[UnclearLine]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "raw": row.raw,
                "ask_message": row.ask_message,
                "suggestion": asdict(row.suggestion) if row.suggestion else None,
            }
        )
    return out


def parse_lines_from_text(raw: str) -> list[LineItem]:
    """Tool #1: 개/EA·원 기준으로 행을 뽑는다. 금액·합계는 amount_ocr(검산용)."""
    found: list[LineItem] = []
    for match in _LINE.finditer(raw or ""):
        item = LineItem(
            name=match.group("name"),
            qty=_to_int(match.group("qty")),
            unit_price=_to_int(match.group("price")),
            amount_ocr=_to_int(match.group("amount")),
        )
        item.recompute()
        found.append(item)
    known = {item.name for item in found}
    for match in _NAMED_QTY.finditer(raw or ""):
        name = (match.group("name") or "").strip()
        if not name or name in known:
            continue
        item = LineItem(name=name, qty=_to_int(match.group("qty")))
        item.recompute()
        found.append(item)
        known.add(name)
    return found


def extract_doc_total_ocr(raw: str) -> int | None:
    """
    문서 레벨 합계/총공급대가.
    품목 줄 안에서 이미 amount로 잡힌 구간은 제외한다.
    """
    text = raw or ""
    occupied: list[tuple[int, int]] = []
    for match in _LINE.finditer(text):
        occupied.append((match.start(), match.end()))

    def _inside(start: int, end: int) -> bool:
        return any(a <= start and end <= b for a, b in occupied)

    candidates: list[int] = []
    for match in _DOC_TOTAL.finditer(text):
        if _inside(match.start(), match.end()):
            continue
        value = _to_int(match.group(1))
        if value is not None:
            candidates.append(value)
    if not candidates:
        return None
    return candidates[-1]


def is_amount_only_mention(text: str) -> bool:
    """금액만 말하고 수량·단가 데이터/수정이 아닐 때."""
    cleaned = (text or "").strip()
    if not _AMOUNT_MENTION.search(cleaned):
        return False
    if parse_lines_from_text(cleaned):
        return False
    # 수정 요청이면 수량을 안 적었어도 edit으로 넘긴다.
    # 처리 가능 여부(수량만 가능)는 Tool #3가 따로 판단한다.
    if _EDIT.search(cleaned):
        return False
    return True


def is_unsupported_edit(text: str) -> bool:
    """수정 요청이지만 1차 범위(수량 조정) 밖인지."""
    return bool(_EDIT_UNSUPPORTED.search(text or ""))


def classify_intent(text: str, *, has_lines: bool) -> Intent:
    """0-1 라우터.

    fill은 텍스트가 아니라 직전 되물음 종류(pending_kind)로 정해지므로
    여기서는 내지 않는다.
    """
    cleaned = (text or "").strip()
    if has_lines and is_amount_only_mention(cleaned):
        return "amount_only"
    if has_lines and _EDIT.search(cleaned):
        return "edit"
    if parse_lines_from_text(cleaned):
        return "data"
    return "chitchat"


def image_fail_reason(
    *, vision_error: bool, ocr_text: str, lines: list[LineItem]
) -> str | None:
    if vision_error:
        return UNREAD_VISION
    if not (ocr_text or "").strip():
        return UNREAD_NO_TEXT
    if not lines:
        return UNREAD_NO_FIELDS
    return None


@dataclass
class Completeness:
    """Tool #2 판정 결과. 되물음 종류를 문구가 아니라 값으로 들고 다닌다."""

    ok: bool
    message: str | None = None
    pending_kind: PendingKind | None = None
    pending_name: str | None = None


def check_completeness(
    lines: list[LineItem],
    *,
    doc_total_ocr: int | None = None,
) -> Completeness:
    """Tool #2. 금액은 필수 아님. 확정은 계산값, OCR 금액은 검산."""
    if not lines:
        return Completeness(False, "품목이 없습니다.")
    for item in lines:
        item.recompute()
        if not item.name or item.qty is None or item.unit_price is None:
            missing = item.name or "해당 품목"
            fillable = bool(item.name)
            if item.qty is None:
                ask = ASK_MISSING_QTY.format(name=missing)
            else:
                ask = ASK_MISSING_PRICE.format(name=missing)
            return Completeness(
                False,
                ask,
                "fill_name" if fillable else None,
                item.name if fillable else None,
            )
        if item.amount_conflict:
            # qty·unit_price는 바로 위에서 None이 아님을 확인했다.
            return Completeness(
                False,
                (
                    f"{item.name} 단가나 수량을 다시 확인 하겠습니다.\n"
                    f"수량 {item.qty}개, 개당 {item.unit_price:,}원으로 "
                    f"총 {item.amount_calc:,}원이 맞습니까?"
                ),
                "conflict",
            )
    calc_total = totals(lines)
    if doc_total_ocr is not None and doc_total_ocr != calc_total:
        return Completeness(
            False,
            (
                f"읽은 합계({doc_total_ocr:,}원)와 품목 계산 합계({calc_total:,}원)가 "
                f"다릅니다. 계산 합계로 할까요?"
            ),
            "conflict",
        )
    return Completeness(True)


def completeness(
    lines: list[LineItem],
    *,
    doc_total_ocr: int | None = None,
) -> tuple[bool, str | None]:
    """되물음 종류가 필요 없는 호출부를 위한 축약형."""
    result = check_completeness(lines, doc_total_ocr=doc_total_ocr)
    return result.ok, result.message


def apply_natural_edit(text: str, lines: list[LineItem]) -> tuple[list[LineItem], str]:
    """Tool #3. 품목 없으면 되물음."""
    match = _QTY_ONLY.search(text or "")
    if not match:
        return lines, ASK_WHICH_ITEM
    named = (match.group("name") or "").strip()
    qty = _to_int(match.group("qty"))
    if not named or qty is None:
        return lines, ASK_WHICH_ITEM
    target = next((item for item in lines if item.name == named), None)
    if target is None:
        return lines, ASK_WHICH_ITEM
    target.qty = qty
    target.recompute()
    return lines, f"네, {target.name} 수량을 {target.qty}개로 수정했습니다."


@dataclass
class UnclearResolution:
    """되물음 큐 첫 항목에 대한 답변 처리 결과.

    resolved가 있으면 확정 처리(큐에서 pop 후 병합). 없으면 여전히 미확정이며
    updated_current로 큐 첫 항목을 갱신하고 reply로 다시 묻는다.
    """

    resolved: list[LineItem] | None = None
    updated_current: UnclearLine | None = None
    reply: str | None = None


def resolve_unclear_answer(answer: str, current: UnclearLine) -> UnclearResolution:
    """미확정 줄 되물음에 대한 답변을 해석한다 (turn.py `_resolve_unclear`와 같은 로직).

    OcrSessionState에 묶이지 않은 순수 함수라 세션 서비스·그래프 노드 양쪽에서
    같은 규칙을 쓸 수 있다.
    """
    if is_affirmative(answer) and current.suggestion is not None:
        return UnclearResolution(resolved=[current.suggestion])

    parsed = parse_lines_from_text(answer)
    # _LINE으로 단가까지 확정 매칭된 경우만 "완전히 새로운 품목"으로 받아들인다.
    # 그렇지 않으면(예: "2box는 2개야") 엉뚱한 품목을 새로 만들지 말고,
    # 지금 제안 중인 품목에 대한 보정 답으로 본다.
    if any(item.unit_price is not None for item in parsed):
        return UnclearResolution(resolved=parsed)

    suggestion = current.suggestion
    if suggestion is None:
        name = guess_item_name(current.raw)
        if name and not name[0].isdigit():
            suggestion = LineItem(name=name)

    if suggestion is not None:
        qty = extract_qty_general(answer)
        price = extract_price_from_text(answer)
        if qty is not None or price is not None:
            if qty is not None:
                suggestion.qty = qty
            if price is not None:
                suggestion.unit_price = price
            suggestion.recompute()
            if suggestion.qty is not None and suggestion.unit_price is not None:
                return UnclearResolution(resolved=[suggestion])
            updated = UnclearLine(
                raw=current.raw,
                suggestion=suggestion,
                ask_message=unclear_ask_message(current.raw, suggestion),
            )
            return UnclearResolution(updated_current=updated, reply=updated.ask_message)

    updated = UnclearLine(raw=current.raw, suggestion=suggestion, ask_message=current.ask_message)
    return UnclearResolution(updated_current=updated, reply=current.ask_message)


def apply_fill(text: str, lines: list[LineItem], pending_name: str) -> list[LineItem]:
    """되물음 답에 있는 수량·단가만 반영. 이번 답의 값이 이전(스테일) 값보다 우선."""
    qty = extract_qty_general(text)
    match = _PRICE_ONLY.search(text or "")
    price = _to_int(match.group("price")) if match else None
    if qty is None and price is None:
        price = _to_int(text)
    unit = extract_qty_unit(text)
    for item in lines:
        if item.name == pending_name:
            if qty is not None:
                item.qty = qty
            if unit:
                item.qty_unit = unit
            if price is not None:
                item.unit_price = price
            item.recompute()
            break
    return lines


def _merge_numeric(
    existing: int | None, incoming: int | None
) -> tuple[int | None, bool]:
    """한쪽만 있으면 채택. 둘 다 있고 다르면 conflict."""
    if existing is None:
        return incoming, False
    if incoming is None:
        return existing, False
    if existing == incoming:
        return existing, False
    return existing, True


def merge_line_lists(
    first: list[LineItem], second: list[LineItem]
) -> tuple[list[LineItem], list[FieldConflict]]:
    """
    같은 이름은 한 줄로 병합.
    필드 한쪽만 채움 → 채택. 둘 다 있고 다름 → FieldConflict.
    """
    by_name: dict[str, LineItem] = {}
    order: list[str] = []
    conflicts: list[FieldConflict] = []

    def _ingest(item: LineItem) -> None:
        item.recompute()
        if item.name not in by_name:
            by_name[item.name] = item
            order.append(item.name)
            return
        base = by_name[item.name]
        qty, qty_conflict = _merge_numeric(base.qty, item.qty)
        price, price_conflict = _merge_numeric(base.unit_price, item.unit_price)
        amount_ocr, _ = _merge_numeric(base.amount_ocr, item.amount_ocr)
        if qty_conflict and base.qty is not None and item.qty is not None:
            conflicts.append(
                FieldConflict(
                    name=item.name, field="qty", options=[base.qty, item.qty]
                )
            )
        if price_conflict and base.unit_price is not None and item.unit_price is not None:
            conflicts.append(
                FieldConflict(
                    name=item.name,
                    field="unit_price",
                    options=[base.unit_price, item.unit_price],
                )
            )
        # 충돌이면 확정 전 빈 값으로 두어 미리보기 차단 + 되물음
        base.qty = None if qty_conflict else qty
        base.unit_price = None if price_conflict else price
        base.amount_ocr = amount_ocr
        base.recompute()

    for item in first:
        _ingest(item)
    for item in second:
        _ingest(item)

    return [by_name[name] for name in order], conflicts


def field_conflict_message(conflict: FieldConflict) -> str:
    label = "단가" if conflict.field == "unit_price" else "수량"
    a, b = conflict.options[0], conflict.options[1]
    if conflict.field == "unit_price":
        return (
            f"{conflict.name} {label}가 다르게 읽혔어요. "
            f"{a:,}원과 {b:,}원 중 어느 게 맞나요?"
        )
    return (
        f"{conflict.name} {label}이 다르게 읽혔어요. "
        f"{a}개와 {b}개 중 어느 게 맞나요?"
    )


def apply_field_conflict_choice(
    text: str, lines: list[LineItem], conflict: FieldConflict
) -> bool:
    """사용자 답에서 옵션을 고르면 True."""
    chosen = _to_int(text)
    if chosen is None:
        match = _PRICE_ONLY.search(text or "")
        chosen = _to_int(match.group("price") if match else None)
    if chosen is None or chosen not in conflict.options:
        return False
    for item in lines:
        if item.name != conflict.name:
            continue
        if conflict.field == "unit_price":
            item.unit_price = chosen
        else:
            item.qty = chosen
        item.recompute()
        return True
    return False


def totals(lines: list[LineItem]) -> int:
    return sum((item.amount_calc or 0) for item in lines)


def newly_completed_items(
    before: list[LineItem], after: list[LineItem]
) -> list[LineItem]:
    """이번 턴에 수량·단가가 막 채워진 품목만. 이미 완결이던 줄은 빼는다."""
    before_by_name = {item.name: item for item in before}

    def _is_complete(item: LineItem) -> bool:
        return item.qty is not None and item.unit_price is not None

    filled: list[LineItem] = []
    for item in after:
        if not _is_complete(item):
            continue
        prev = before_by_name.get(item.name)
        if prev is None or not _is_complete(prev):
            filled.append(item)
    return filled


def format_just_filled_preview_reply(
    items: list[LineItem], *, kind_selected: bool
) -> str:
    """전체 확정 안내 — 이번 턴에 채운 품목만 요약한다."""
    summaries: list[str] = []
    for item in items:
        if item.qty is None or item.unit_price is None:
            continue
        calc = item.amount_calc
        if calc is None:
            calc = item.qty * item.unit_price
        unit = item.qty_unit or "개"
        summaries.append(
            f"{item.name}, {item.qty}{unit}, 단가 {item.unit_price:,}원, 총 {calc:,}원 입니다."
        )
    if not summaries:
        return ""
    footer = PREVIEW_PLEASE if kind_selected else KIND_READY
    return "\n".join([*summaries, "내용을 확인하세요.", footer])


def lines_as_dicts(lines: list[LineItem]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in lines:
        item.recompute()
        out.append(asdict(item))
    return out


def extract_qty_from_text(text: str) -> int | None:
    match = _QTY_ONLY.search(text or "")
    if not match:
        return None
    return _to_int(match.group("qty"))


def extract_qty_general(text: str) -> int | None:
    """단위 있는 수량 우선, 없으면 단위 없는 앞숫자("2 3000원" → 2)."""
    cleaned = text or ""
    m = _SUGGEST_QTY.search(cleaned)
    if m:
        return _to_int(m.group("qty"))
    from_unit = extract_qty_from_text(cleaned)
    if from_unit is not None:
        return from_unit
    bare = _BARE_LEADING_QTY.match(cleaned)
    if bare:
        return _to_int(bare.group("qty"))
    return None


def extract_qty_unit(text: str) -> str | None:
    """수량 뒤에 붙은 단위 단어. 없으면 None (안내문은 '개'로 폴백)."""
    match = _SUGGEST_QTY.search(text or "")
    if not match:
        return None
    unit = (match.group("qty_unit") or "").strip()
    return unit or None


def extract_price_from_text(text: str) -> int | None:
    match = _PRICE_ONLY.search(text or "")
    if not match:
        return None
    return _to_int(match.group("price"))


def guess_item_name(text: str) -> str:
    """수량·단가가 있으면 그 앞까지, 없으면 줄 전체를 품목명으로 본다."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    matched = re.match(
        rf"(?P<name>{_NAME_WORDS})(?=\s+(?:수량\s*)?\d+\s*{_QTY_UNIT_ALT}|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if matched:
        return matched.group("name").strip()
    return cleaned


def is_affirmative(text: str) -> bool:
    return bool(AFFIRM.search(text or ""))


def is_negative(text: str) -> bool:
    """예/아니오 질문의 부정 답. 긍정과 동시에 맞으면 긍정 우선."""
    cleaned = text or ""
    if is_affirmative(cleaned):
        return False
    return bool(_DENY.search(cleaned))


def is_greeting(text: str) -> bool:
    return bool(_GREETING.search(text or ""))


def accept_calculated_amounts(lines: list[LineItem]) -> list[LineItem]:
    """되물음에서 동의하면 확정 금액을 계산값으로 맞춘다."""
    for item in lines:
        if item.amount_conflict and item.amount_calc is not None:
            item.amount_ocr = item.amount_calc
            item.recompute()
    return lines


def is_image_upload(filename: str | None, mime: str | None) -> bool:
    lowered_mime = (mime or "").lower()
    if lowered_mime.startswith("image/"):
        return True
    name = (filename or "").lower()
    return name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"))
