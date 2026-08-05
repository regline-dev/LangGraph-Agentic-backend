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
    document_kind: int = Field(
        1,
        ge=1,
        le=4,
        description="1 일반텍스트 · 2 스캔/이미지 · 3 표 · 4 복합레이아웃",
    )
    structure_labels: list[str] = Field(
        default_factory=list,
        description="구조 지문 — 헤더·라벨 이름만 (값 제외)",
    )
    extracted_metadata: list[dict[str, str]] = Field(
        default_factory=list,
        description="문서 구조에서 확인한 메타데이터 후보 [{label, value, source}]",
    )
    template_match_status: str = Field(
        "no_match",
        description="match | ambiguous | no_match",
    )
    template_id: str | None = Field(None, description="맞음일 때 템플릿 id")
    template_prompt: str | None = Field(None, description="맞음일 때 잠금 프롬프트")
    prompt_locked: bool = Field(False, description="맞음이면 프롬프트 수정 불가")
    template_candidates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="애매일 때 후보 [{template_id, name}]",
    )
    text_excerpt: str = Field(
        "",
        description="문서 텍스트 발췌 (UI 지시문 채움용)",
    )
    result_schema: dict[str, Any] | None = Field(
        None,
        description="맞음일 때 결과 양식 템플릿 (확정 JSON 구조)",
    )
    filled_result: dict[str, Any] | None = Field(
        None,
        description="맞음+결과양식일 때 서버가 이번 PDF 값으로 채운 메타 (자동 표시용)",
    )


class PdfSaveTemplateRequest(BaseModel):
    """양식 저장 — 판별용 labels + 결과 양식 및/또는 탐색 지시문."""

    template_id: str = Field(..., min_length=1)
    name: str = Field("")
    labels: list[str] = Field(default_factory=list)
    prompt: str = Field("", description="탐색 지시문(결과 양식 없을 때·레거시)")
    result_schema: dict[str, Any] | None = Field(
        None,
        description="결과 양식 템플릿 (확정 메타 JSON)",
    )


class PdfSaveTemplateResponse(BaseModel):
    """양식 저장 결과."""

    template_id: str
    name: str
    labels: list[str]
    saved: bool = True
    has_result_schema: bool = False


class PdfDeleteTemplateResponse(BaseModel):
    """템플릿 soft-delete / 벡터 삭제 결과."""

    template_id: str
    soft_deleted: bool = True
    delete_vectors: bool = False
    deleted_vector_points: int = 0


class PdfTemplateListItem(BaseModel):
    """템플릿 목록 한 건."""

    template_id: str
    name: str = ""
    metadata_name: str = Field("", description="METADATA_NAME 정규화(UPPER)")
    labels: list[str] = Field(default_factory=list)
    has_result_schema: bool = False
    result_schema: dict[str, Any] | None = None


class PdfTemplateListResponse(BaseModel):
    """GET /pdf/templates."""

    templates: list[PdfTemplateListItem] = Field(default_factory=list)
