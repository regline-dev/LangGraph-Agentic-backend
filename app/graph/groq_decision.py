"""Groq LLM — llm_decision용 decide_fn.

OpenAI-compatible API (https://api.groq.com/openai/v1)로
검색 필요 여부·질의어·답변을 JSON으로 받는다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.graph.nodes import DecideFn
from app.graph.state import AgentState

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_SYSTEM_PROMPT = """당신은 PDF 문서 검색 에이전트 판단기다.
사용자 질문을 보고 검색(Tool)이 필요한지 판단한다.

반드시 JSON 객체만 출력한다. 다른 문장·마크다운 설명 금지.
형식:
{"need_search": true또는false, "search_query": "검색어", "answer": "최종답변또는빈문자열"}

규칙:
- 인사·자기소개·잡담처럼 문서 근거가 불필요하면 need_search=false 이고 answer에 답변을 채운다.
- 문서 내용(제도·기간·규정 등)이 필요하면 need_search=true, search_query에 검색어, answer는 "".
- observations(이전 검색 결과)가 있으면 그걸 근거로 need_search=false와 answer를 채우거나, 부족하면 need_search=true로 재검색한다.
"""


def parse_decision_json(raw: str) -> dict[str, Any]:
    """LLM 응답 텍스트에서 판단 JSON을 파싱한다."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("Groq 응답이 비어 JSON을 파싱할 수 없습니다.")

    # ```json ... ``` 펜스 제거
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 본문 중 `{...}`만 추출 시도
        brace = re.search(r"\{[\s\S]*\}", text)
        if not brace:
            raise ValueError(f"Groq 응답이 JSON이 아닙니다: {raw[:200]}") from None
        try:
            data = json.loads(brace.group(0))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Groq 응답 JSON 파싱 실패: {raw[:200]}") from exc

    if not isinstance(data, dict):
        raise ValueError("Groq 판단 JSON은 객체여야 합니다.")

    return {
        "need_search": bool(data.get("need_search", False)),
        "search_query": str(data.get("search_query", "") or "").strip(),
        "answer": str(data.get("answer", "") or "").strip(),
    }


def make_groq_decide_fn(
    *,
    api_key: str,
    model: str,
    client: Any | None = None,
) -> DecideFn:
    """Groq를 호출하는 decide_fn을 만든다.

    Args:
        api_key: GROQ_API_KEY
        model: GROQ_MODEL
        client: 테스트용 OpenAI 호환 클라이언트 주입 (없으면 생성)
    """
    cleaned_key = (api_key or "").strip()
    if not cleaned_key:
        raise ValueError("GROQ_API_KEY가 비어 있습니다. .env에 GROQ_API_KEY를 설정하세요.")

    cleaned_model = (model or "").strip() or "llama-3.3-70b-versatile"
    chat_client = client or _create_groq_client(cleaned_key)

    def decide(state: AgentState) -> dict[str, Any]:
        user_payload = {
            "question": state.get("question", ""),
            "tool_call_count": int(state.get("tool_call_count") or 0),
            "observations": state.get("observations") or [],
        }
        completion = chat_client.chat.completions.create(
            model=cleaned_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            temperature=0.0,
            max_tokens=512,
        )
        content = ""
        if completion.choices:
            content = (completion.choices[0].message.content or "").strip()
        return parse_decision_json(content)

    return decide


def make_groq_decide_fn_from_settings() -> DecideFn:
    """app.config Settings로 Groq decide_fn을 만든다."""
    from app.config import get_settings

    settings = get_settings()
    return make_groq_decide_fn(api_key=settings.groq_api_key, model=settings.groq_model)


def _create_groq_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("openai 패키지가 필요합니다. pip install openai") from exc

    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
