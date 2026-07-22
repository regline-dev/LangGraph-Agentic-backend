"""지표·카드 질문 판별 및 질문 속 우화 제목 추출."""

from __future__ import annotations

# (kind, 매칭 키워드) — 긴/구체적 키워드를 앞에
# 「최종평가」를 「평가」보다 먼저 둬야 오인 방지
_METRIC_KINDS: list[tuple[str, tuple[str, ...]]] = [
    ("final_grade", ("최종평가",)),
    ("content_eval", ("내용평가", "평가는", "평가")),
    ("fun", ("재미도", "재미는")),
    ("violence", ("폭력성",)),
    ("moral", ("교훈 명확도", "교훈명확도")),
    ("ending_tone", ("결말톤",)),
    ("keywords", ("키워드",)),
    ("characters", ("등장인물",)),
    ("reading", ("낭독시간", "예상 낭독")),
    ("dialogue", ("대사비중",)),
    ("length", ("분량",)),
    ("video", ("영상화",)),
    # 단독 "교훈"은 줄거리 교훈과 겹칠 수 있어 내용평가·명확도 다음에 둔다
    ("moral", ("교훈",)),
]


def detect_metric_kind(question: str) -> str | None:
    """지표/카드 질문이면 kind, 아니면 None."""
    text = (question or "").strip()
    if not text:
        return None
    for kind, keywords in _METRIC_KINDS:
        for keyword in keywords:
            if keyword in text:
                return kind
    return None


def extract_title_from_question(question: str, known_titles: list[str]) -> str | None:
    """질문에 포함된 우화 제목 — 가장 긴 매칭 우선.

    완전 일치 후, 마지막 글자 누락 등 접두 부분일치(짧으면 제외).
    """
    text = (question or "").strip()
    if not text or not known_titles:
        return None
    ordered = sorted({t.strip() for t in known_titles if t and t.strip()}, key=len, reverse=True)
    for title in ordered:
        if title in text:
            return title

    # 부분일치: 「아버지와 아들」→「아버지와 아들들」
    fuzzy_hits: list[str] = []
    for title in ordered:
        stem = title[:-1] if len(title) >= 5 else ""
        if stem and len(stem) >= 4 and stem in text:
            fuzzy_hits.append(title)
            continue
        # 질문 전체가 제목 접두인 경우 (제목만 입력·오타)
        if len(text) >= 4 and title.startswith(text) and text != title:
            fuzzy_hits.append(title)

    if not fuzzy_hits:
        return None
    # 가장 긴 후보 1개 (동률이면 정렬상 앞)
    fuzzy_hits.sort(key=len, reverse=True)
    if len(fuzzy_hits) == 1:
        return fuzzy_hits[0]
    # 여러 개면 최장만 (나머지는 오탐 가능성)
    longest = fuzzy_hits[0]
    if all(longest.startswith(other) or other.startswith(longest) for other in fuzzy_hits[1:]):
        return longest
    return longest
