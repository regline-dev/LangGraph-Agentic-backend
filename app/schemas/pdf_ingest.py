"""PDF ingest / inspect API 응답 스키마."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PdfIngestResponse(BaseModel):
    """적재 결과."""

    source_file: str = Field(..., description="uploads에 저장된 파일명")
    indexed: int = Field(..., ge=0, description="적재된 청크 수")
    collection: str = Field(..., description="Qdrant 컬렉션명")
    page_count: int = Field(0, ge=0, description="PDF 페이지 수")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="이솝 우화 카드 특화 메타(없으면 null)",
    )
    basic_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="기본 메타(페이지·파일명·글자수)",
    )
    is_fable_card: bool = Field(False, description="우화 카드 파싱 성공 여부")


class PdfInspectResponse(BaseModel):
    """적재 없이 형식 검사."""

    is_fable_card: bool
    page_count: int = Field(..., ge=0)
    basic_metadata: dict[str, Any] = Field(default_factory=dict)
    fable_metadata: dict[str, Any] | None = None
