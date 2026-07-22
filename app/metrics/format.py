"""metadata → 사용자 답변 문구."""

from __future__ import annotations

from typing import Any


def clarify_which_fable(kind: str) -> str:
    """우화 미특정 시 되묻기."""
    labels = {
        "content_eval": "내용평가",
        "fun": "재미도",
        "violence": "폭력성",
        "moral": "교훈 명확도",
        "ending_tone": "결말톤",
        "keywords": "키워드",
        "final_grade": "최종평가",
        "characters": "등장인물",
        "reading": "낭독시간",
        "dialogue": "대사비중",
        "length": "분량",
        "video": "영상화 적합도",
    }
    label = labels.get(kind, "정보")
    return f"어떤 우화의 {label}를 알고 싶으신가요?"


def format_metric_answer(meta: dict[str, Any], kind: str) -> str:
    """조회된 metadata로 답변 문자열을 만든다."""
    title = str(meta.get("title") or "이 우화")
    keywords = _keywords_list(meta)

    if kind == "content_eval":
        return (
            f"「{title}」 내용평가입니다.\n"
            f"- 재미도: {meta.get('fun')}/5\n"
            f"- 폭력성: {meta.get('violence')}/5\n"
            f"- 교훈 명확도: {meta.get('moral_clarity')}/5\n"
            f"- 결말톤: {meta.get('ending_tone')}"
        )
    if kind == "fun":
        return f"「{title}」 재미도는 {meta.get('fun')}/5 입니다."
    if kind == "violence":
        return f"「{title}」 폭력성은 {meta.get('violence')}/5 입니다."
    if kind == "moral":
        return f"「{title}」 교훈 명확도는 {meta.get('moral_clarity')}/5 입니다."
    if kind == "ending_tone":
        return f"「{title}」 결말톤은 {meta.get('ending_tone')} 입니다."
    if kind == "keywords":
        joined = ", ".join(keywords) if keywords else "(없음)"
        return f"「{title}」 키워드: {joined}"
    if kind == "final_grade":
        return f"「{title}」 최종평가는 {meta.get('final_grade')} 입니다."
    if kind == "characters":
        return f"「{title}」 등장인물은 {meta.get('characters_count')}명 입니다."
    if kind == "reading":
        return f"「{title}」 예상 낭독시간은 {meta.get('reading_seconds')}초 입니다."
    if kind == "dialogue":
        return f"「{title}」 대사비중은 {meta.get('dialogue_ratio')}% 입니다."
    if kind == "length":
        return f"「{title}」 분량은 {meta.get('char_count')}자 입니다."
    if kind == "video":
        return (
            f"「{title}」 영상화 관련: 낭독 {meta.get('reading_seconds')}초, "
            f"등장인물 {meta.get('characters_count')}명, 대사비중 {meta.get('dialogue_ratio')}%, "
            f"최종평가 {meta.get('final_grade')}"
        )
    return f"「{title}」에 대한 해당 정보를 찾지 못했습니다."


def _keywords_list(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("keywords")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str) and raw.strip():
        return [part for part in raw.split("|") if part.strip()]
    return []
