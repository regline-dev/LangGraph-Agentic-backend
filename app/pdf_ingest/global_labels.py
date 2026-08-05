"""전역 라벨(GLOBAL_LABELS.json) 로딩 · result_schema 정규화 · template_id 규칙."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# data/GLOBAL_LABELS.json (레포 기준)
_DEFAULT_LABELS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "GLOBAL_LABELS.json"
)

SEARCH_LABELS_KEY = "search_labels"

# 구 키 → 신 키 (한 번만 이전)
_LEGACY_KEY_MAP = {
    "created_date": "pdf_created_at",
    "modify_date": "pdf_updated_at",
    "SCHEMA": "METADATA_NAME",
}

# 문서특성 숫자 → template_id 접두 문자
DOC_KIND_LETTER: dict[int, str] = {
    1: "A",
    2: "B",
    3: "C",
    4: "D",
}

_login_safe_re = re.compile(r"[^A-Za-z0-9_-]+")


def load_global_labels(path: Path | None = None) -> dict[str, str]:
    """GLOBAL_LABELS.json → 삽입 순서 유지 dict (영문키→한글명)."""
    target = path or _DEFAULT_LABELS_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GLOBAL_LABELS.json 은 객체여야 합니다.")
    out: dict[str, str] = {}
    for key, value in raw.items():
        k = str(key).strip()
        if not k:
            continue
        out[k] = "" if value is None else str(value)
    if not out:
        raise ValueError("GLOBAL_LABELS.json 이 비어 있습니다.")
    return out


def global_label_keys(path: Path | None = None) -> list[str]:
    """전역 키 목록 (파일 순서)."""
    return list(load_global_labels(path).keys())


def doc_kind_to_letter(document_kind: int | str | None) -> str:
    """1~4 → A~D. 그 외는 X."""
    try:
        kind = int(document_kind)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "X"
    return DOC_KIND_LETTER.get(kind, "X")


def sanitize_login_id(login_id: str | None, *, fallback: str = "guest") -> str:
    """template_id에 넣을 로그인 id (영숫자·_- 만)."""
    raw = (login_id or "").strip() or fallback
    cleaned = _login_safe_re.sub("_", raw).strip("_")
    return cleaned or fallback


def build_template_id(
    *,
    document_kind: int | str | None,
    login_id: str | None,
    timestamp_ms: int,
) -> str:
    """예: C_counsel1_1785541236324"""
    letter = doc_kind_to_letter(document_kind)
    user = sanitize_login_id(login_id)
    return f"{letter}_{user}_{int(timestamp_ms)}"


def normalize_metadata_name(raw: str | None) -> str:
    """메타데이터 템플릿명 — 공백 제거 + UPPER."""
    if raw is None:
        return ""
    return "".join(str(raw).split()).upper()


def extract_metadata_name_from_schema(schema: dict[str, Any] | None) -> str:
    """result_schema에서 METADATA_NAME(또는 구 SCHEMA) 정규화 값."""
    if not isinstance(schema, dict):
        return ""
    raw = schema.get("METADATA_NAME")
    if raw is None or str(raw).strip() == "":
        raw = schema.get("SCHEMA")
    return normalize_metadata_name(raw if raw is None else str(raw))


def normalize_result_schema(
    source: dict[str, Any] | None,
    *,
    labels_path: Path | None = None,
) -> dict[str, Any]:
    """전역 키 전부(빈값 '') + GLOBAL 순서 + 가변 키 + search_labels 맨 끝.

    구 created_date/modify_date 값은 pdf_created_at/pdf_updated_at 으로 이전.
    """
    labels = load_global_labels(labels_path)
    global_keys = list(labels.keys())
    src: dict[str, Any] = dict(source) if isinstance(source, dict) else {}

    # 레거시 키 이전 (신 키가 비어 있을 때만)
    for old_key, new_key in _LEGACY_KEY_MAP.items():
        if old_key not in src:
            continue
        if new_key not in src or src.get(new_key) in (None, ""):
            src[new_key] = src[old_key]
        del src[old_key]

    search_labels = src.pop(SEARCH_LABELS_KEY, None)
    if search_labels is not None and not isinstance(search_labels, dict):
        search_labels = {}

    ordered: dict[str, Any] = {}
    for key in global_keys:
        value = src.pop(key, "")
        ordered[key] = "" if value is None else value

    # METADATA_NAME 정규화 (공백 제거·UPPER)
    if "METADATA_NAME" in ordered and ordered["METADATA_NAME"] not in (None, ""):
        ordered["METADATA_NAME"] = normalize_metadata_name(str(ordered["METADATA_NAME"]))

    # 가변 키 (전역·search_labels 제외) — 입력 순서 유지
    for key, value in list(src.items()):
        k = str(key)
        if k == SEARCH_LABELS_KEY:
            continue
        ordered[k] = value

    if isinstance(search_labels, dict):
        ordered[SEARCH_LABELS_KEY] = dict(search_labels)

    return ordered
