"""POST /fable/generate-pdf 요청 스키마."""

from pydantic import BaseModel, Field


class FableGeneratePdfRequest(BaseModel):
    """클라이언트가 id를 보내지 않는다 — 서버 자동 채번."""

    body_text: str = Field(..., description="우화 원문 텍스트")
    source_note: str | None = Field(
        default=None,
        description="원문 출처 각주 (없으면 기본 문구)",
    )
