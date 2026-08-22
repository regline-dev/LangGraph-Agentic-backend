"""원문 → 채점 → PDF 파일 (CLI run_pipeline 과 동일 흐름)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Any, Callable

from app.fable_pdf.metadata_stamp import stamp_metadata_name_on_pdf
from app.fable_pdf.pdf_generator import generate_fable_pdf
from app.fable_pdf.pdf_type_profile import (
    PdfTypeProfile,
    is_aesop_type,
)
from app.fable_pdf.scorer import score_fable_with_llm
from app.fable_pdf.typed_pdf import generate_typed_pdf

SOURCE_NOTE_DEFAULT = "1867년 타운센드 영역본 기반 우리말 번역, 이솝우화 도감"

FablePipelineFn = Callable[[str, int, str, str], dict[str, Any]]


def _title_from_body(body_text: str) -> str:
    """원문 첫 비어 있지 않은 줄."""
    for line in (body_text or "").splitlines():
        text = line.strip()
        if text:
            return text
    return ""


def _groups_from_filled_configs(type_profile: PdfTypeProfile) -> dict[str, dict[str, str]]:
    """표에 이미 있는 이름·값으로 PDF 그룹을 만든다. LLM 없음."""
    groups: dict[str, dict[str, str]] = {}
    for cfg in type_profile.configs:
        name = str(cfg.get("group_name") or "").strip()
        if not name:
            continue
        if "value" in cfg:
            value = str(cfg.get("value") or "").strip()
        else:
            value = str(cfg.get("values_text") or "").strip()
        groups[name] = {"내용": value}
    return groups


def _subtitles_from_profile(type_profile: PdfTypeProfile) -> dict[str, str]:
    """생성 시 LLM을 안 타므로 수동 내용만 넣고, 비면 빈 문자열."""
    out: dict[str, str] = {}
    for item in type_profile.subtitles:
        title_key = str(item.get("title") or "").strip()
        if not title_key:
            continue
        out[title_key] = str(item.get("content") or "").strip()
    return out


def _header_fields(type_profile: PdfTypeProfile | None, type_code: str) -> dict[str, Any]:
    """문서 상단·스탬프용 공통 필드."""
    return {
        "type_code": type_code,
        "type_updated_at": (
            type_profile.type_updated_at if type_profile is not None else None
        ),
        "type_updated_by": (
            type_profile.type_updated_by if type_profile is not None else None
        ),
        "document_created_date": datetime.now().strftime("%Y-%m-%d"),
    }


def run_fable_pipeline(
    body_text: str,
    fable_id: int,
    output_path: str,
    source_note: str = SOURCE_NOTE_DEFAULT,
    *,
    timeout_seconds: float = 100.0,
    type_profile: PdfTypeProfile | None = None,
    preview_score: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Groq 채점 후 PDF를 output_path에 쓴다.
    완료 파일에 METADATA_NAME(=type_code) 스탬프.
    """

    def _work() -> dict[str, Any]:
        note = source_note or SOURCE_NOTE_DEFAULT
        if is_aesop_type(type_profile):
            if preview_score:
                scored = preview_score
            else:
                scored = score_fable_with_llm(body_text, timeout_seconds=timeout_seconds)
            type_code = (
                type_profile.type_code if type_profile is not None else "aesop"
            )
            data = {
                "id": fable_id,
                "body_text": body_text,
                "source_note": note,
                **_header_fields(type_profile, type_code),
                **scored,
            }
            generate_fable_pdf(data, output_path)
            meta_name = stamp_metadata_name_on_pdf(output_path, type_code)
            return {
                "title": str(scored.get("title") or ""),
                "fun": scored.get("fun"),
                "violence": scored.get("violence"),
                "moral_clarity": scored.get("moral_clarity"),
                "ending_tone": scored.get("ending_tone"),
                "metadata_name": meta_name,
            }

        assert type_profile is not None
        # 커스텀 Groq는 구성 만들기(draft)만. 생성은 표 값으로만 PDF.
        scored = {
            "title": _title_from_body(body_text),
            "groups": _groups_from_filled_configs(type_profile),
            "subtitles": _subtitles_from_profile(type_profile),
            "tags": [],
        }
        group_layouts = {}
        for cfg in type_profile.configs:
            group_name = str(cfg.get("group_name") or "").strip()
            if group_name:
                group_layouts[group_name] = str(cfg.get("layout") or "vertical")
        data = {
            "id": fable_id,
            "body_text": body_text,
            "source_note": note,
            "type_name": type_profile.type_name,
            "group_layouts": group_layouts,
            **_header_fields(type_profile, type_profile.type_code),
            **scored,
        }
        generate_typed_pdf(data, output_path)
        meta_name = stamp_metadata_name_on_pdf(output_path, type_profile.type_code)
        return {
            "title": str(scored.get("title") or ""),
            "metadata_name": meta_name,
        }

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_work)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeout as exc:
            raise TimeoutError(
                f"채점·PDF 생성이 {int(timeout_seconds)}초를 초과했습니다."
            ) from exc
