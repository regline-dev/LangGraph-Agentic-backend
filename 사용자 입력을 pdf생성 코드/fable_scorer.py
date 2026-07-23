"""
LLM 채점 함수

fable_pdf_generator.generate_fable_pdf()가 요구하는 필드 중
"내용 평가"에 해당하는 것들(fun/violence/moral_clarity/ending_tone/tags/modern_take)은
원문을 읽어야만 알 수 있는 값이라 LLM 호출이 필요하다.
"구조 정보"(분량/낭독시간/대사비중/최종평가)는 fable_pdf_generator.py 안에서
글자수 계산만으로 이미 자동 처리되므로 여기서 다루지 않는다.
"""
import json
import re

from langchain_groq import ChatGroq

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
  "tags": ["교훈 키워드 1~3개 — 반드시 한글만(한자·중국어 금지). 예: 탐욕, 무지, 결과"],
  "characters": ["등장인물 또는 등장동물 목록, 원문에 실제로 등장하는 것만"],
  "modern_take": "이 상황을 오늘날에 빗대면 어떤 상황인지, 캐주얼한 말투로 2문장 이내"
}}"""


def _get_llm() -> ChatGroq:
    # 프로젝트의 app/llm.py get_llm()과 같은 패턴.
    # GROQ_API_KEY는 환경변수 또는 .env에서 읽음.
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)


def _extract_json(raw: str) -> dict:
    """LLM 응답에 ```json 코드블록이 섞여 나와도 안전하게 JSON만 뽑아낸다."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    return json.loads(cleaned)


def score_fable_with_llm(body_text: str, llm: ChatGroq | None = None) -> dict:
    """
    원문 텍스트를 받아 PDF 생성에 필요한 내용평가 필드를 LLM으로 채점한다.

    반환값 예시:
        {
          "fun": 2, "violence": 3, "moral_clarity": 5,
          "ending_tone": "새드",
          "tags": ["권력남용", "자기합리화", "부당함"],
          "characters": ["늑대", "어린양"],
          "modern_take": "상사가 트집 잡아 부당해고하는 상황이랑 비슷함..."
        }
    """
    llm = llm or _get_llm()
    result = llm.invoke(SCORE_PROMPT.format(body_text=body_text))
    scored = _extract_json(result.content)

    # 최소한의 방어적 검증 - 값이 범위 밖이거나 필드가 비어있으면 여기서 걸러냄
    for key in ("fun", "violence", "moral_clarity"):
        scored[key] = max(0, min(5, int(scored.get(key, 0))))
    if scored.get("ending_tone") not in ("해피", "중립", "새드"):
        scored["ending_tone"] = "중립"
    scored.setdefault("title", "")
    scored.setdefault("subtitle", "")
    scored.setdefault("tags", [])
    scored.setdefault("characters", [])
    scored.setdefault("modern_take", "")
    # CLI 폴더도 한글 키워드 정규화 (app 패키지 경로에서 import)
    try:
        from app.fable_pdf.keyword_normalize import normalize_keyword_tags

        if not isinstance(scored["tags"], list):
            scored["tags"] = [str(scored["tags"])]
        scored["tags"] = normalize_keyword_tags(scored["tags"])
    except ImportError:
        if not scored["tags"]:
            scored["tags"] = ["우화"]

    return scored


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("사용법: python fable_scorer.py <원문.txt>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()

    print(json.dumps(score_fable_with_llm(text), ensure_ascii=False, indent=2))
