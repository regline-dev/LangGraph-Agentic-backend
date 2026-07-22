"""MBTI 유형별 해석 — LLM 생성 (원문/기본 modern 참고)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# 테스트에서 주입: (title, origin, modern, mbti) -> str
ReinterpretFn = Callable[..., str]


def reinterpret_fable_for_mbti(
    *,
    title: str,
    origin_text: str,
    modern_text: str,
    mbti: str,
    llm_fn: ReinterpretFn | None = None,
    client: Any | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """MBTI 관점으로 재해석한다.

    입력 핵심: 문서 한마디 결론 + MBTI.
    출력 제약: 한국어 두 문장, 합계 70자 이내. 톤 표·랜덤 없음 — 유형 뉘앙스는 LLM이 판단.
    """
    if llm_fn is not None:
        return llm_fn(
            title=title,
            origin=origin_text,
            modern=modern_text,
            mbti=mbti,
        )

    from app.config import get_settings
    from app.graph.groq_decision import _create_groq_client

    settings = get_settings()
    key = (api_key or settings.groq_api_key or "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY가 없어 MBTI 재해석을 할 수 없습니다.")
    used_model = (model or settings.groq_model or "").strip() or "llama-3.3-70b-versatile"
    chat = client or _create_groq_client(key)
    mbti_code = (mbti or "").strip().upper() or "UNKNOWN"

    system = (
        "이솝 우화의 「한마디 결론」을 사용자 MBTI 관점으로 다시 쓴다. "
        "반드시 한국어 두 문장만. 두 문장 합쳐 공백 포함 70자 이내. "
        "MBTI 성격 설명·유형 나열·장황한 분석 금지. "
        "해당 유형이라면 어떻게 받아들일지 뉘앙스만 담는다. "
        "마크다운·JSON·따옴표 장식 금지. 원문 복붙 금지."
    )
    user = (
        f"우화 제목: {title}\n"
        f"사용자 MBTI: {mbti_code}\n\n"
        f"[한마디 결론]\n{modern_text[:400]}\n\n"
        f"[원문 참고]\n{origin_text[:500]}\n\n"
        f"위 「한마디 결론」을 {mbti_code} 시점으로 두 문장·70자 이내로만 다시 써라."
    )
    completion = chat.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
        max_tokens=120,
    )
    content = ""
    if completion.choices:
        content = (completion.choices[0].message.content or "").strip()
    if not content:
        return f"「{title}」에 대한 {mbti_code} 유형별 해석을 만들지 못했습니다."
    return f"[{mbti_code} 유형별 해석] 「{title}」\n{content}"
