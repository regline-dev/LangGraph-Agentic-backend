"""POST /fable/generate-pdf 요청 스키마."""

from pydantic import BaseModel, Field


class PdfConfigGroupIn(BaseModel):
    group_name: str = Field(..., description="구성 그룹명")
    values_text: str = Field(default="", description="쉼표 구분 항목 라벨 또는 채워진 값")
    value: str | None = Field(
        default=None, description="그룹 단위 채움값(세부항목 없을 때). 라벨 목록과 같으면 본문이 아님"
    )
    fields: dict[str, str] | None = Field(
        default=None, description="미리보기와 같은 세부항목 라벨→값"
    )
    chart: str | None = Field(default="none")
    layout: str | None = Field(default="vertical")
    sort_order: int | None = Field(default=None)


class PdfSubtitleIn(BaseModel):
    title: str = Field(..., description="서브타이틀 제목")
    mode: str | None = Field(default="llm", description="llm | manual")
    content: str | None = Field(default="", description="수동 입력 시 본문")


class FableGeneratePdfRequest(BaseModel):
    """클라이언트가 id를 보내지 않는다 — 서버 자동 채번."""

    body_text: str = Field(..., description="원문 텍스트")
    source_note: str | None = Field(
        default=None,
        description="원문 출처 각주 (없으면 기본 문구)",
    )
    # 타입 미전달 = 구버전 → 이솝 경로. type_code=aesop 도 이솝 경로.
    type_code: str | None = Field(default=None, description="PDF 타입 코드")
    type_name: str | None = Field(default=None, description="PDF 타입 표시명")
    configs: list[PdfConfigGroupIn] | None = Field(
        default=None, description="타입 구성 그룹"
    )
    subtitles: list[PdfSubtitleIn] | None = Field(
        default=None, description="서브타이틀 블록"
    )
    # 문서 상단 — 타입 updated_* (프론트가 DB에서 넘김)
    type_updated_at: str | None = Field(default=None, description="타입 수정 시각")
    type_updated_by: str | None = Field(default=None, description="타입 수정자")
    # 미리보기에서 받은 채점. 있으면 생성 시 Groq를 다시 타지 않는다
    preview_score: dict | None = Field(default=None, description="미리보기 LLM 채점 결과")


class FablePreviewLlmRequest(BaseModel):
    """미리보기 클릭 시점 LLM — 이솝 채점 / 커스텀은 보낸 구성 이름에 값만."""

    body_text: str = Field(..., description="원문 텍스트")
    type_code: str | None = Field(default=None, description="PDF 타입 코드")
    type_name: str | None = Field(default=None, description="PDF 타입 표시명")
    configs: list[PdfConfigGroupIn] | None = Field(
        default=None, description="사람이 정한 구성 그룹. 없으면 커스텀은 값을 안 뽑음"
    )
    subtitles: list[PdfSubtitleIn] | None = Field(
        default=None, description="사람이 정한 서브타이틀. 있으면 그 제목에 값만"
    )


class FableDraftConfigsRequest(BaseModel):
    """커스텀 구성 초안 — 원문에서 항목·값·차트를 한 번에 뽑는다."""

    body_text: str = Field(..., description="원문 텍스트")
    type_code: str | None = Field(default=None, description="PDF 타입 코드")
    type_name: str | None = Field(default=None, description="PDF 타입 표시명")
