"""키워드(tags) 한글 정규화 — 한자·중국어 단독 태그 제거/치환."""

from __future__ import annotations

import re

# CJK 통합 한자
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
# 한글 음절·자모
_HANGUL_RE = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]+")

# 자주 나오는 한자 키워드 → 한글 (채점 LLM 버릇 보정)
_HANJA_TO_HANGUL: dict[str, str] = {
    "貪欲": "탐욕",
    "贪欲": "탐욕",
    "無知": "무지",
    "结果": "결과",
    "結果": "결과",
    "權力": "권력",
    "正直": "정직",
    "勤勉": "근면",
    "傲慢": "오만",
    "虚荣": "허영",
    "虛榮": "허영",
    "谎言": "거짓말",
    "謊言": "거짓말",
    "诚实": "정직",
    "誠實": "정직",
}


def normalize_keyword_tags(tags: list | None) -> list[str]:
    """키워드는 한글만 남긴다. 한자만 있으면 치환표 또는 제외."""
    if not tags:
        return ["우화"]

    cleaned: list[str] = []
    for raw in tags:
        text = str(raw or "").strip()
        if not text:
            continue
        mapped = _HANJA_TO_HANGUL.get(text)
        if mapped:
            cleaned.append(mapped)
            continue
        if _CJK_RE.search(text) and not _HANGUL_RE.search(text):
            # 한자만 → 표에 없으면 스킵
            continue
        # 한글+한자 섞임 → 한자만 제거
        if _CJK_RE.search(text):
            text = _CJK_RE.sub("", text).strip()
            text = re.sub(r"\s+", " ", text)
            if not text:
                continue
        cleaned.append(text)

    # 중복 제거(순서 유지)
    unique: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)

    return unique[:3] if unique else ["우화"]
