"""MBTI 설정·변경 안내 채팅 명령."""

from __future__ import annotations

import re
from typing import Any

from app.metrics.memory import FableSessionMemory

# MBTI : infp / MBTI：ENFJ / mbti=intj
_SET_PATTERN = re.compile(
    r"^\s*MBTI\s*[:：=]\s*([IE][NS][TF][JP])\s*$",
    re.IGNORECASE,
)

# 「설정변경」처럼 mbti 단어 없이 쓰던 단독 안내 (하위 호환)
_HELP_EXACT = frozenset({"설정변경", "유형변경"})

# mbti/유형 + 변경·설정 의도 — 목록 추가 없이 변형 흡수
# 「유형별 해석」은 제외 (변경 의도가 아님)
_HELP_INTENT_PATTERN = re.compile(
    r"(?:"
    r"mbti|"
    r"유형(?!별)"  # '유형별' 제외
    r")"
    r".{0,24}?"
    r"(?:"
    r"바꾸|바꿀|바꿔|바꿨|바뀌|"  # 바꾸다 활용
    r"변경|수정|설정|"
    r"하고싶|할래|할까|해줘|해봐|"
    r"보려면|보고싶|싶어"
    r")",
    re.IGNORECASE,
)


def _is_mbti_help_request(normalized: str) -> bool:
    """공백 제거된 질문 기준 — 안내 템플릿이 필요한지."""
    if not normalized:
        return False
    if normalized in _HELP_EXACT:
        return True
    # 유형별 해석 / 재해석은 안내가 아니라 verbatim 경로
    if "유형별해석" in normalized or "재해석" in normalized:
        return False
    return _HELP_INTENT_PATTERN.search(normalized) is not None


def try_handle_mbti_command(
    question: str,
    *,
    session_id: str | None,
    memory: FableSessionMemory,
) -> dict[str, Any] | None:
    """설정/안내 명령이면 {answer, citations, mbti}, 아니면 None."""
    cleaned = (question or "").strip()
    if not cleaned:
        return None

    match = _SET_PATTERN.match(cleaned)
    if match:
        if not session_id or not str(session_id).strip():
            return {
                "answer": "세션이 없어 MBTI를 저장할 수 없습니다. 채팅창을 다시 연 뒤 입력해 주세요.",
                "citations": [],
                "mbti": None,
            }
        code = match.group(1).upper()
        memory.set_mbti(session_id, code)
        return {
            "answer": f"{code}로 저장했습니다.",
            "citations": [],
            "mbti": code,
        }

    normalized = re.sub(r"\s+", "", cleaned.lower())
    if _is_mbti_help_request(normalized):
        current = memory.get_mbti(session_id)
        if current:
            answer = (
                "MBTI를 바꾸려면 아래처럼 입력하세요.\n"
                f"수정 예시) MBTI : enfj\n"
                f"현재 설정: {current}"
            )
        else:
            answer = (
                "MBTI를 설정하려면 아래처럼 입력하세요.\n"
                "입력 예시) MBTI : infp"
            )
        return {
            "answer": answer,
            "citations": [],
            "mbti": current,
        }

    return None
