"""/agent/chat 요청·응답 스키마."""

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """PDF 모드 사용자 질문."""

    question: str = Field(..., min_length=1, description="사용자 질문")


class Citation(BaseModel):
    """검색 근거."""

    source_file: str = ""
    page: int = 0
    snippet: str = ""


class AgentChatResponse(BaseModel):
    """Agentic 검색 최종 응답."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
