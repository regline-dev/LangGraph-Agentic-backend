"""이솝 우화 분석 카드 텍스트 → metadata + 원문/현대 본문 분리."""

from __future__ import annotations

import re
from typing import Any

# 키워드·본문 구간을 끊을 때 쓰는 섹션 라벨 (시작 일치)
_SECTION_LABELS: tuple[str, ...] = (
    "영상화 적합도",
    "예상 낭독시간",
    "등장인물",
    "대사비중",
    "분량",
    "최종평가",
    "내용 평가",
    "원문",
    "한마디 결론",
    "오늘날로 치면",  # 하위 호환
    "키워드",
    "재미도",
    "폭력성",
    "교훈 명확도",
    "결말톤",
    "난이도",
    "몰입도",
    "일반 영상",
)

_FABLE_ID_RE = re.compile(r"이솝우화\s*#\s*(\d+)")
_BADGE_TONE_RE = re.compile(r"^결말톤\s*:\s*(.+)$")
_INT_RE = re.compile(r"\d+")


def parse_fable_card(text: str) -> dict[str, Any] | None:
    """우화 카드면 metadata + origin_text/modern_text dict, 아니면 None.

    Returns:
        fable_id, title, ending_tone, fun, violence, moral_clarity,
        reading_seconds, characters_count, dialogue_ratio, char_count,
        final_grade, keywords(list[str]), origin_text, modern_text
    """
    if not text or not text.strip():
        return None

    lines = [line.rstrip() for line in text.splitlines()]
    # 빈 줄은 인덱스 유지용으로 남기되, 매칭은 strip 기준
    if not any(_FABLE_ID_RE.search(line) for line in lines):
        return None
    if not any(line.strip() == "원문" for line in lines):
        return None

    fable_id = _first_int_from_match(lines, _FABLE_ID_RE)
    ending_tone, title = _parse_badge_and_title(lines)
    if fable_id is None or not title or not ending_tone:
        return None

    fun = _value_after_label(lines, "재미도", as_int=True)
    violence = _value_after_label(lines, "폭력성", as_int=True)
    moral_clarity = _value_after_label(lines, "교훈 명확도", as_int=True)
    reading_seconds = _value_after_label(lines, "예상 낭독시간", as_int=True)
    characters_count = _value_after_label(lines, "등장인물", as_int=True)
    dialogue_ratio = _value_after_label(lines, "대사비중", as_int=True)
    char_count = _value_after_label(lines, "분량", as_int=True)
    final_grade = _value_after_label(lines, "최종평가", as_int=False)
    keywords = _collect_keywords(lines)

    origin_text, modern_text = _split_origin_modern(lines)
    if not origin_text.strip():
        return None

    required_ints = [
        fun,
        violence,
        moral_clarity,
        reading_seconds,
        characters_count,
        dialogue_ratio,
        char_count,
    ]
    if any(value is None for value in required_ints) or final_grade is None:
        return None

    return {
        "fable_id": fable_id,
        "title": title,
        "ending_tone": ending_tone,
        "fun": fun,
        "violence": violence,
        "moral_clarity": moral_clarity,
        "reading_seconds": reading_seconds,
        "characters_count": characters_count,
        "dialogue_ratio": dialogue_ratio,
        "char_count": char_count,
        "final_grade": final_grade,
        "keywords": keywords,
        "origin_text": origin_text.strip(),
        "modern_text": modern_text.strip(),
    }


def parse_fable_metadata(text: str) -> dict[str, Any] | None:
    """계획서 이름 — 본문 필드 없이 metadata만 (테스트·외부용)."""
    parsed = parse_fable_card(text)
    if parsed is None:
        return None
    return {
        key: value
        for key, value in parsed.items()
        if key not in {"origin_text", "modern_text"}
    }


def _parse_badge_and_title(lines: list[str]) -> tuple[str | None, str | None]:
    """'결말톤: OO' 배지와 다음 줄 제목."""
    for index, line in enumerate(lines):
        match = _BADGE_TONE_RE.match(line.strip())
        if not match:
            continue
        tone = match.group(1).strip()
        title = None
        if index + 1 < len(lines):
            title = lines[index + 1].strip() or None
        return tone, title
    return None, None


def _value_after_label(
    lines: list[str],
    label: str,
    *,
    as_int: bool,
) -> int | str | None:
    """라벨 줄(완전 일치) 다음 비어 있지 않은 줄을 값으로 쓴다."""
    for index, line in enumerate(lines):
        if line.strip() != label:
            continue
        for next_line in lines[index + 1 :]:
            stripped = next_line.strip()
            if not stripped:
                continue
            if as_int:
                found = _INT_RE.search(stripped)
                return int(found.group(0)) if found else None
            return stripped
    return None


def _collect_keywords(lines: list[str]) -> list[str]:
    """'키워드' 다음부터 다음 섹션 라벨 전까지."""
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == "키워드":
            start = index + 1
            break
    if start is None:
        return []

    keywords: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_section_label(stripped):
            break
        keywords.append(stripped)
    return keywords


def _is_section_label(line: str) -> bool:
    for label in _SECTION_LABELS:
        if line == label or line.startswith(label):
            return True
    return False


# modern 섹션 라벨 (신규 + 하위 호환)
_MODERN_SECTION_LABELS: frozenset[str] = frozenset({"한마디 결론", "오늘날로 치면"})


def _split_origin_modern(lines: list[str]) -> tuple[str, str]:
    """원문 ~ modern 라벨 직전 / modern 라벨 다음 ~ 끝(※ 제외)."""
    origin_start: int | None = None
    modern_start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "원문" and origin_start is None:
            origin_start = index + 1
        elif stripped in _MODERN_SECTION_LABELS and modern_start is None:
            modern_start = index + 1

    if origin_start is None:
        return "", ""

    if modern_start is None:
        origin_lines = lines[origin_start:]
        modern_lines: list[str] = []
    else:
        origin_lines = lines[origin_start : modern_start - 1]
        modern_lines = lines[modern_start:]

    modern_lines = [
        line for line in modern_lines if line.strip() and not line.strip().startswith("※")
    ]
    return "\n".join(origin_lines).strip(), "\n".join(modern_lines).strip()


def _first_int_from_match(lines: list[str], pattern: re.Pattern[str]) -> int | None:
    for line in lines:
        match = pattern.search(line)
        if match:
            return int(match.group(1))
    return None
