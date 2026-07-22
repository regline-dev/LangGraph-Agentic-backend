"""PDF 모드 도메인 분류 — 이솝우화 vs ARKK holdings (Phase D)."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal

PdfDomain = Literal["fable", "holdings"]

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_DOMAIN_SYSTEM_PROMPT = """당신은 PDF 모드 질문 분류기다.
질문이 어느 문서 영역인지 판별한다.

반드시 JSON 객체만 출력한다.
형식: {"domain": "fable" 또는 "holdings"}

규칙:
- domain="fable": 이솝 우화, 우화 제목·줄거리·재미도·내용평가·MBTI·한마디 결론·우화 목록 등
- domain="holdings": ARKK·ETF·종목·비중·보유·holdings·주식지표·테슬라 비중 등 ETF 보유 PDF
- 애매하면 우화 관련 단서가 있으면 fable, ETF/종목/비중 단서가 있으면 holdings
"""

# 테스트·Groq 실패 폴백용 키워드
_HOLDINGS_PATTERN = re.compile(
    r"(?i)\b(arkk|etf|holdings|innovation)\b|"
    r"비중|종목|보유|주식|시가총액|펀드|테슬라|\btsla\b|\broku\b|\bbeam\b",
)
_FABLE_PATTERN = re.compile(
    r"우화|이솝|재미도|내용평가|한마디\s*결론|mbti|원문|현대|교훈|"
    r"늑대|양|여우|목록|전체\s*목록",
)

ClassifyFn = Callable[[str], PdfDomain]


def parse_domain_json(raw: str) -> PdfDomain:
    """LLM 응답에서 domain 파싱."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("도메인 분류 응답이 비어 있습니다.")

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        brace = re.search(r"\{[\s\S]*\}", text)
        if not brace:
            raise ValueError(f"도메인 JSON 파싱 실패: {raw[:200]}") from None
        data = json.loads(brace.group(0))

    if not isinstance(data, dict):
        raise ValueError("도메인 JSON은 객체여야 합니다.")

    domain = str(data.get("domain", "")).strip().lower()
    if domain not in ("fable", "holdings"):
        raise ValueError(f"알 수 없는 domain: {domain!r}")
    return domain  # type: ignore[return-value]


def classify_pdf_domain_heuristic(question: str) -> PdfDomain:
    """키워드 기반 분류 — 단위테스트·Groq 폴백."""
    text = (question or "").strip()
    if not text:
        return "fable"

    holdings_hit = bool(_HOLDINGS_PATTERN.search(text))
    fable_hit = bool(_FABLE_PATTERN.search(text))

    if holdings_hit and not fable_hit:
        return "holdings"
    if fable_hit and not holdings_hit:
        return "fable"
    if holdings_hit and fable_hit:
        # ETF 이름이 우화 제목보다 우선 (예: ARKK 비중)
        if re.search(r"(?i)\barkk\b|etf|holdings|비중|종목", text):
            return "holdings"
        return "fable"
    return "fable"


def make_groq_domain_classify_fn(
    *,
    api_key: str,
    model: str,
    client: Any | None = None,
) -> ClassifyFn:
    """Groq로 domain 분류 함수를 만든다."""
    cleaned_key = (api_key or "").strip()
    if not cleaned_key:
        raise ValueError("GROQ_API_KEY가 비어 있습니다.")

    cleaned_model = (model or "").strip() or "llama-3.3-70b-versatile"
    chat_client = client or _create_groq_client(cleaned_key)

    def classify(question: str) -> PdfDomain:
        completion = chat_client.chat.completions.create(
            model=cleaned_model,
            messages=[
                {"role": "system", "content": _DOMAIN_SYSTEM_PROMPT},
                {"role": "user", "content": (question or "").strip()},
            ],
            temperature=0.0,
            max_tokens=64,
        )
        content = ""
        if completion.choices:
            content = (completion.choices[0].message.content or "").strip()
        return parse_domain_json(content)

    return classify


def classify_pdf_domain(
    question: str,
    *,
    classify_fn: ClassifyFn | None = None,
) -> PdfDomain:
    """PDF 모드 질문의 도메인을 반환한다."""
    if classify_fn is not None:
        return classify_fn(question)

    from app.config import get_settings

    settings = get_settings()
    api_key = (settings.groq_api_key or "").strip()
    if not api_key:
        return classify_pdf_domain_heuristic(question)

    try:
        groq_fn = make_groq_domain_classify_fn(api_key=api_key, model=settings.groq_model)
        return groq_fn(question)
    except Exception:  # noqa: BLE001 — 폴백
        return classify_pdf_domain_heuristic(question)


def _create_groq_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("openai 패키지가 필요합니다.") from exc

    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
