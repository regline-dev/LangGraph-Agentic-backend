"""/agent/chat 요청·응답 스키마."""

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """PDF 모드 사용자 질문."""

    question: str = Field(..., min_length=1, description="사용자 질문")
    # 단기 메모리(직전 우화 제목) — UI 세션 UUID 권장
    session_id: str | None = Field(default=None, description="대화 세션 ID")


class Citation(BaseModel):
    """검색 근거."""

    source_file: str = ""
    page: int = 0
    snippet: str = ""
    # Qdrant 벡터 유사도 (규칙 경로·미검색이면 0)
    score: float = 0.0


class AgentChatResponse(BaseModel):
    """Agentic 검색 최종 응답."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    # 세션 단기 메모리의 현재 MBTI (없으면 null) — UI 안내글용
    mbti: str | None = None
    # citations 중 최고 score (UI 유사도 표시·임계 판단용)
    similarity: float = 0.0
