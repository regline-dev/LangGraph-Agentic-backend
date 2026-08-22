"""PDF 생성 요청의 타입 프로필.

type_code=aesop 은 시드·기존 이솝 분석 카드 경로 유지용.
그 외 타입은 구성(configs)·서브타이틀로 채점·레이아웃한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# 시드 pdf_types.type_code 와 동일. 이솝 전용 파이프라인 분기용.
AESOP_TYPE_CODE = "aesop"


@dataclass(frozen=True)
class PdfTypeProfile:
    type_code: str
    type_name: str
    configs: list[dict[str, Any]] = field(default_factory=list)
    subtitles: list[dict[str, Any]] = field(default_factory=list)
    # 문서 상단 표시용 — DB pdf_types.updated_*
    type_updated_at: str | None = None
    type_updated_by: str | None = None


def is_aesop_type(profile: PdfTypeProfile | None) -> bool:
    """구버전(프로필 없음)과 aesop 코드는 이솝 전용 경로."""
    if profile is None:
        return True
    return (profile.type_code or "").strip().lower() == AESOP_TYPE_CODE


def configs_have_explicit_values(profile: PdfTypeProfile) -> bool:
    """프론트가 칸 값을 이미 실어 보냈으면 생성 시 LLM을 다시 타지 않는다."""
    return any(cfg.get("value") is not None for cfg in (profile.configs or []))


def parse_values_text(values_text: str | None) -> list[str]:
    """쉼표 구분 한글 라벨 목록."""
    if not values_text:
        return []
    return [part.strip() for part in str(values_text).split(",") if part.strip()]


def profile_from_request(
    *,
    type_code: str | None,
    type_name: str | None,
    configs: list[dict[str, Any]] | None,
    subtitles: list[dict[str, Any]] | None,
    type_updated_at: str | None = None,
    type_updated_by: str | None = None,
) -> PdfTypeProfile | None:
    """요청 필드 → 프로필. type_code·type_name 둘 다 없으면 None(구버전)."""
    code = (type_code or "").strip()
    name = (type_name or "").strip()
    if not code and not name:
        return None
    return PdfTypeProfile(
        type_code=code or "custom",
        type_name=name or code or "PDF",
        configs=list(configs or []),
        subtitles=list(subtitles or []),
        type_updated_at=(str(type_updated_at).strip() if type_updated_at else None)
        or None,
        type_updated_by=(str(type_updated_by).strip() if type_updated_by else None)
        or None,
    )
