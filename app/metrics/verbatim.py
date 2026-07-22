"""원문 / MBTI 유형별 해석(modern) — 본문 그대로 또는 MBTI LLM 재해석."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.metrics.detect import extract_title_from_question
from app.metrics.memory import FableSessionMemory

FetchBodyFn = Callable[[str, str], dict[str, Any] | None]
# (title, origin, modern, mbti) -> answer
ReinterpretFn = Callable[..., str]


def wants_mbti_reinterpret(question: str) -> bool:
    """유형별 LLM 재해석 트리거인지 — 한마디 결론은 여기 포함하지 않음."""
    text = (question or "").strip()
    if not text:
        return False
    if "MBTI 유형별 해석" in text or "유형별 해석" in text:
        return True
    if "재해석" in text:
        return True
    return False


def detect_verbatim_content_type(question: str) -> str | None:
    """그대로/유형별 해석할 본문 종류: origin | modern | None.

    내용·줄거리·원문·그대로·읽어 → origin 본문 그대로 (LLM 요약 금지).
    한마디·재해석·유형별 → modern (MBTI 있으면 try_handle에서 LLM 유형별).
    내용평가는 metric 경로이므로 여기서 origin으로 잡지 않음.
    """
    text = (question or "").strip()
    if not text:
        return None
    # MBTI 유형별 해석 / 재해석 (= content_type=modern, LLM은 별도)
    if wants_mbti_reinterpret(text):
        return "modern"
    if "한마디 결론" in text or "한마디결론" in text:
        return "modern"
    # 「한마디」단독·수식은 modern (단독 「결론」은 vague 되묻기)
    if "한마디" in text:
        return "modern"
    if "오늘날로 치면" in text or "오늘날로치면" in text:
        return "modern"
    if "현대해석" in text or "현대 해석" in text:
        return "modern"
    # 사용자가 자주 쓰는 말: 내용·줄거리 (+ 하위 호환 원문·낭독)
    if "내용평가" in text:
        return None
    if (
        "내용" in text
        or "줄거리" in text
        or "원문" in text
        or "그대로" in text
        or "읽어" in text
        or "본문" in text
        or "낭독" in text
    ):
        return "origin"
    return None


def try_handle_verbatim_body(
    question: str,
    *,
    session_id: str | None,
    memory: FableSessionMemory,
    known_titles: list[str],
    fetch_fn: FetchBodyFn,
    reinterpret_fn: ReinterpretFn | None = None,
) -> dict[str, Any] | None:
    """해당하면 {answer, citations, mbti?}, 아니면 None."""
    cleaned = (question or "").strip()
    if not cleaned:
        return None

    content_type = detect_verbatim_content_type(cleaned)
    if content_type is None:
        return None

    mentioned = extract_title_from_question(cleaned, known_titles)
    if mentioned:
        memory.set_title(session_id, mentioned)

    title = mentioned or memory.get_title(session_id)
    label = "내용(원문)" if content_type == "origin" else "한마디 결론·유형별 해석"
    if not title:
        return {
            "answer": f"어떤 우화의 {label}을 보고 싶으신가요?",
            "citations": [],
            "mbti": memory.get_mbti(session_id),
        }

    fetched = fetch_fn(title, content_type)
    if not fetched or not str(fetched.get("text") or "").strip():
        return {
            "answer": f"「{title}」의 해당 본문을 찾지 못했습니다.",
            "citations": [],
            "mbti": memory.get_mbti(session_id),
        }

    memory.set_title(session_id, title)
    body_text = str(fetched["text"]).strip()
    mbti = memory.get_mbti(session_id)

    # modern(한마디·재해석·유형별) + MBTI 설정 → LLM 유형별 해석
    # MBTI 없으면 문서 modern 그대로
    if content_type == "modern" and mbti and reinterpret_fn is not None:
        origin_fetched = fetch_fn(title, "origin") or {}
        origin_text = str(origin_fetched.get("text") or "").strip()
        answer = reinterpret_fn(
            title=title,
            origin=origin_text,
            modern=body_text,
            mbti=mbti,
        )
        return {
            "answer": answer,
            "citations": [],
            "mbti": mbti,
        }

    # origin 항상 그대로 / modern + MBTI 없음 → 카드 modern 그대로
    return {
        "answer": body_text,
        "citations": list(fetched.get("citations") or []),
        "mbti": mbti,
    }
