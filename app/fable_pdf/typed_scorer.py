"""타입 구성 라벨 기반 LLM 채점 (비이솝)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from langchain_groq import ChatGroq

from app.fable_pdf.keyword_normalize import normalize_keyword_tags
from app.fable_pdf.pdf_type_profile import PdfTypeProfile, parse_values_text
from app.fable_pdf.scorer import _extract_json, _get_llm

# 상세 흐름 로그 — 이벤트 로그와 별개
DEBUG_ONOFF = os.getenv("DEBUG_ONOFF") == "1"
# 콜론 왼쪽이 항목명. URL 스킴은 제외.
_COLON_LABEL_LINE = re.compile(r"^([^:]{1,40}):\s*(.*)$")
_SKIP_LABEL_PREFIXES = ("http", "https", "mailto")


def build_typed_score_prompt(body_text: str, profile: PdfTypeProfile) -> str:
    """구성·서브타이틀 스키마를 JSON 출력 지시로 만든다. 이솝 고정 필드 강제 금지."""
    group_schema: dict[str, dict[str, str]] = {}
    for cfg in profile.configs:
        group_name = str(cfg.get("group_name") or "").strip()
        if not group_name:
            continue
        labels = parse_values_text(cfg.get("values_text"))
        if not labels:
            # 값 목록이 비면 그룹 단위 요약 문자열
            group_schema[group_name] = {"요약": "원문에서 추출한 짧은 문장"}
        else:
            group_schema[group_name] = {
                label: f"{label}에 해당하는 값을 원문에서 추출 (없으면 빈 문자열)"
                for label in labels
            }

    subtitle_titles = [
        str(item.get("title") or "").strip()
        for item in profile.subtitles
        if str(item.get("title") or "").strip()
    ]
    # 수동 입력이 있으면 프롬프트에 '그대로 유지' 안내
    manual_notes = []
    for item in profile.subtitles:
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        mode = str(item.get("mode") or "llm").strip().lower()
        if title and content and mode != "llm":
            manual_notes.append(f'- "{title}": 이미 확정된 문장 → "{content}" 를 그대로 쓸 것')

    schema_json = json.dumps(
        {
            "title": "문서 제목 (원문 첫 줄에 있으면 그대로)",
            "groups": group_schema,
            "subtitles": {t: f"{t} 내용을 원문 기반으로 1~2문장" for t in subtitle_titles},
            "tags": ["핵심 키워드 1~3개, 한글만"],
        },
        ensure_ascii=False,
        indent=2,
    )

    manual_block = ""
    if manual_notes:
        manual_block = "\n서브타이틀 고정값:\n" + "\n".join(manual_notes) + "\n"

    return f"""다음은 「{profile.type_name}」 유형 문서의 원문이다.
아래 JSON 형식으로만 채워라. 다른 설명·코드블록 표시는 붙이지 마라.
우화 분석용 고정 점수 스키마는 쓰지 말고, 위에 제시한 groups·subtitles 키만 채워라.
원문에 없는 값은 빈 문자열로 둔다.
{manual_block}
원문:
{body_text}

출력 형식(JSON만):
{schema_json}
"""


def normalize_typed_score(
    raw: dict[str, Any],
    profile: PdfTypeProfile,
) -> dict[str, Any]:
    """LLM 응답을 PDF용 dict로 정규화."""
    title = str(raw.get("title") or "").strip()
    groups_in = raw.get("groups") if isinstance(raw.get("groups"), dict) else {}
    groups_out: dict[str, dict[str, str]] = {}
    for cfg in profile.configs:
        group_name = str(cfg.get("group_name") or "").strip()
        if not group_name:
            continue
        labels = parse_values_text(cfg.get("values_text"))
        src = groups_in.get(group_name) if isinstance(groups_in.get(group_name), dict) else {}
        if not labels:
            summary = ""
            if isinstance(src, dict):
                summary = str(src.get("요약") or next(iter(src.values()), "") or "")
            groups_out[group_name] = {"요약": summary}
        else:
            groups_out[group_name] = {
                label: str((src or {}).get(label) or "").strip() for label in labels
            }

    subs_in = raw.get("subtitles") if isinstance(raw.get("subtitles"), dict) else {}
    subs_out: dict[str, str] = {}
    for item in profile.subtitles:
        title_key = str(item.get("title") or "").strip()
        if not title_key:
            continue
        manual = str(item.get("content") or "").strip()
        mode = str(item.get("mode") or "llm").strip().lower()
        if manual and mode != "llm":
            subs_out[title_key] = manual
        else:
            subs_out[title_key] = str((subs_in or {}).get(title_key) or manual or "").strip()

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = normalize_keyword_tags(
        [str(t) for t in tags], empty_fallback=None
    )

    return {
        "title": title,
        "groups": groups_out,
        "subtitles": subs_out,
        "tags": tags,
    }


def score_typed_with_llm(
    body_text: str,
    profile: PdfTypeProfile,
    *,
    llm: ChatGroq | None = None,
    timeout_seconds: float = 100.0,
) -> dict[str, Any]:
    """원문 + 타입 구성 → groups/subtitles/title."""
    llm = llm or _get_llm(timeout_seconds=timeout_seconds)
    prompt = build_typed_score_prompt(body_text, profile)
    result = llm.invoke(prompt)
    content = getattr(result, "content", result)
    if not isinstance(content, str):
        content = str(content)
    scored = _extract_json(content)
    return normalize_typed_score(scored, profile)


# 화면 CHART_OPTIONS 와 동일. 타입명 분기가 아니라 허용 값 집합.
_ALLOWED_CHARTS = frozenset({"none", "radar", "bar", "pie", "line"})


def _is_colon_label_line(line: str) -> re.Match[str] | None:
    """`이름: 나머지` 줄이면 매치. 콜론 오른쪽 목록은 항목명이 아니다."""
    text = (line or "").strip()
    matched = _COLON_LABEL_LINE.match(text)
    if not matched:
        return None
    name = matched.group(1).strip()
    if not name or name.lower() in _SKIP_LABEL_PREFIXES:
        return None
    return matched


def _title_from_body(body_text: str) -> str:
    """원문 첫 비어 있지 않은 줄."""
    for line in (body_text or "").splitlines():
        text = line.strip()
        if text:
            return text
    return ""


def overlay_colon_labeled_draft(
    body_text: str, drafted: dict[str, Any] | None = None
) -> dict[str, Any]:
    """원문에 `이름: …` 줄이 있으면 그 왼쪽만 항목으로 덮어쓴다. 특정 이름 분기는 없다."""
    parsed = parse_colon_labeled_items(body_text)
    base = drafted if isinstance(drafted, dict) else {}
    if not parsed:
        return base
    return normalize_typed_draft(
        {
            "title": str(base.get("title") or "").strip() or _title_from_body(body_text),
            "items": parsed,
            "tags": base.get("tags") or [],
        }
    )


def parse_colon_labeled_items(body_text: str) -> list[dict[str, str]]:
    """콜론 왼쪽만 항목명으로 뽑는다. 값은 다음 빈 줄 전까지의 문장."""
    lines = (body_text or "").splitlines()
    items: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        matched = _is_colon_label_line(lines[index])
        if not matched:
            index += 1
            continue
        name = matched.group(1).strip()
        value_parts: list[str] = []
        index += 1
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                break
            if _is_colon_label_line(stripped):
                break
            value_parts.append(stripped)
            index += 1
        items.append(
            {
                "name": name,
                "value": " ".join(value_parts).strip(),
                "chart": "none",
            }
        )
    return items


def build_typed_draft_prompt(body_text: str, type_name: str) -> str:
    """원문에서 항목 이름·값·차트 여부를 한 번에 뽑는 지시. 이솝 점수 스키마 금지."""
    display_name = (type_name or "").strip() or "문서"
    return f"""다음은 「{display_name}」 유형 문서의 원문이다.
아래 JSON 형식으로만 채워라. 다른 설명·코드블록 표시는 붙이지 마라.
우화 분석용 고정 점수 스키마는 쓰지 마라.
`이름: 가, 나, 다` 형태면 항목 이름은 콜론 왼쪽뿐이다. 가·나·다는 항목으로 만들지 마라.
값은 그 다음 문장이다. 콜론 오른쪽 목록을 값으로 쓰지 마라.
콜론이 없는 소개 문단은 항목이 아니다.
없는 값은 만들지 마라.
chart는 none, radar, bar, pie, line 중 하나다. 숫자가 여러 개로 비교될 때만 none이 아닌 값을 쓴다.

원문:
{body_text}

출력 형식(JSON만):
{{
  "title": "문서 제목 (원문 첫 줄에 있으면 그대로)",
  "items": [
    {{"name": "항목 이름", "value": "원문에 있는 값", "chart": "none"}}
  ],
  "tags": ["핵심 키워드 1~3개, 한글만"]
}}
"""


def normalize_typed_draft(raw: dict[str, Any]) -> dict[str, Any]:
    """초안 LLM 응답 → 화면 표용 항목 목록."""
    title = str(raw.get("title") or "").strip()
    items_in = raw.get("items") if isinstance(raw.get("items"), list) else []
    items_out: list[dict[str, str]] = []
    for item in items_in:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        # 이름만 있고 값이 빈 항목은 구성이 아님 — 뽑지 않는다
        if not name or not value:
            continue
        chart = str(item.get("chart") or "none").strip().lower()
        if chart not in _ALLOWED_CHARTS:
            chart = "none"
        items_out.append(
            {
                "name": name,
                "value": value,
                "chart": chart,
            }
        )
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = normalize_keyword_tags([str(t) for t in tags], empty_fallback=None)
    return {"title": title, "items": items_out, "tags": tags}


def draft_typed_items_with_llm(
    body_text: str,
    type_name: str,
    *,
    llm: ChatGroq | None = None,
    timeout_seconds: float = 100.0,
) -> dict[str, Any]:
    """원문(+타입 표시명) → 항목 이름·값·차트. 생성 PDF와 별도 1회 호출."""
    parsed_items = parse_colon_labeled_items(body_text)
    if parsed_items:
        drafted = overlay_colon_labeled_draft(body_text, {"tags": []})
        names = [
            str(item.get("name") or "").strip()
            for item in (drafted.get("items") or [])
            if str(item.get("name") or "").strip()
        ]
        print(
            "\n".join(
                [
                    f"[{datetime.now(timezone.utc).isoformat()}] event=PDF 구성 초안 LLM",
                    "  api=POST /fable/draft-configs",
                    f"  type_name={(type_name or '-').strip() or '-'}",
                    f"  body_chars={len(body_text or '')}",
                    "  result=success",
                    f"  item_count={len(names)}",
                    f"  items={', '.join(names) if names else '(없음)'}",
                    "  reason=colon_label_parse",
                ]
            ),
            flush=True,
        )
        if DEBUG_ONOFF:
            print(
                "\n".join(
                    [
                        f"[{datetime.now(timezone.utc).isoformat()}] debug=PDF 구성 초안",
                        "  step=colon_label_parse",
                        "  llm=skipped",
                    ]
                ),
                flush=True,
            )
        return drafted

    llm = llm or _get_llm(timeout_seconds=timeout_seconds)
    prompt = build_typed_draft_prompt(body_text, type_name)
    print(
        "\n".join(
            [
                f"[{datetime.now(timezone.utc).isoformat()}] event=PDF 구성 초안 LLM",
                "  api=POST /fable/draft-configs",
                f"  type_name={(type_name or '-').strip() or '-'}",
                f"  body_chars={len(body_text or '')}",
                "  result=requested",
            ]
        ),
        flush=True,
    )
    result = llm.invoke(prompt)
    content = getattr(result, "content", result)
    if not isinstance(content, str):
        content = str(content)
    scored = _extract_json(content)
    drafted = overlay_colon_labeled_draft(body_text, normalize_typed_draft(scored))
    names = [
        str(item.get("name") or "").strip()
        for item in (drafted.get("items") or [])
        if str(item.get("name") or "").strip()
    ]
    print(
        "\n".join(
            [
                f"[{datetime.now(timezone.utc).isoformat()}] event=PDF 구성 초안 LLM",
                "  api=POST /fable/draft-configs",
                f"  type_name={(type_name or '-').strip() or '-'}",
                "  result=success",
                f"  item_count={len(names)}",
                f"  items={', '.join(names) if names else '(없음)'}",
            ]
        ),
        flush=True,
    )
    return drafted

