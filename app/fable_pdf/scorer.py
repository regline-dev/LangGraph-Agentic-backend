"""원문 → Groq 채점 (내용 평가 필드)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_groq import ChatGroq

from app.config import get_settings
from app.fable_pdf.keyword_normalize import normalize_keyword_tags

SCORE_PROMPT = """다음은 짧은 우화(또는 동화) 원문이다. 아래 JSON 형식으로만 평가하라. 다른 설명은 붙이지 마라.

원문:
{body_text}

출력 형식(JSON만, 코드블록 표시 없이):
{{
  "title": "우화 제목 (원문에 이미 제목이 있으면 그대로, 없으면 내용 기반으로 짧게 생성)",
  "subtitle": "한 줄 부제, 15자 내외로 이야기의 핵심을 요약",
  "fun": 0~5 사이 정수 (재미도),
  "violence": 0~5 사이 정수 (폭력성 - 신체적 위해, 위협, 죽음 등의 정도),
  "moral_clarity": 0~5 사이 정수 (교훈이 얼마나 명확하게 드러나는가),
  "ending_tone": "해피" 또는 "중립" 또는 "새드" 중 하나,
  "tags": ["교훈 키워드 1~3개 — 반드시 한글만(한자·중국어·일본어 금지). 예: 탐욕, 무지, 결과"],
  "characters": ["등장인물 또는 등장동물 목록, 원문에 실제로 등장하는 것만"],
  "modern_take": "이 상황을 오늘날에 빗대면 어떤 상황인지, 캐주얼한 말투로 2문장 이내"
}}"""


def _get_llm(*, timeout_seconds: float) -> ChatGroq:
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_model or "llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=settings.groq_api_key or None,
        request_timeout=timeout_seconds,
    )


def _extract_json(raw: str) -> dict[str, Any]:
    """LLM 응답에 ```json 코드블록이 섞여 나와도 JSON만 뽑는다."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    return json.loads(cleaned)


def score_fable_with_llm(
    body_text: str,
    *,
    llm: ChatGroq | None = None,
    timeout_seconds: float = 100.0,
) -> dict[str, Any]:
    """원문을 채점해 PDF 생성에 필요한 내용평가 필드를 반환한다."""
    llm = llm or _get_llm(timeout_seconds=timeout_seconds)
    result = llm.invoke(SCORE_PROMPT.format(body_text=body_text))
    content = getattr(result, "content", result)
    if not isinstance(content, str):
        content = str(content)
    scored = _extract_json(content)

    for key in ("fun", "violence", "moral_clarity"):
        scored[key] = max(0, min(5, int(scored.get(key, 0))))
    if scored.get("ending_tone") not in ("해피", "중립", "새드"):
        scored["ending_tone"] = "중립"
    scored.setdefault("title", "")
    scored.setdefault("subtitle", "")
    scored.setdefault("tags", [])
    scored.setdefault("characters", [])
    scored.setdefault("modern_take", "")
    if not isinstance(scored["tags"], list):
        scored["tags"] = [str(scored["tags"])]
    scored["tags"] = normalize_keyword_tags(scored["tags"])
    if not isinstance(scored["characters"], list):
        scored["characters"] = []
    return scored
