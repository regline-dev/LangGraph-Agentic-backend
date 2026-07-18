"""POST /agent/chat — PDF Agentic 검색 HTTP 진입점."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.graph.runtime import AgentRunner, get_agent_runner
from app.schemas.agent import AgentChatRequest, AgentChatResponse, Citation

router = APIRouter(tags=["agent"])


@router.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(
    body: AgentChatRequest,
    runner: AgentRunner = Depends(get_agent_runner),
) -> AgentChatResponse:
    """질문을 LangGraph Agentic 검색으로 처리한다."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question이 비어 있습니다.")

    try:
        result = runner(question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — API 경계에서 안내
        raise HTTPException(
            status_code=502,
            detail=f"Agent 실행 실패: {exc}",
        ) from exc

    citations_raw = result.get("citations") or []
    citations = [
        Citation(
            source_file=str(item.get("source_file", "")),
            page=int(item.get("page") or 0),
            snippet=str(item.get("snippet", "")),
        )
        for item in citations_raw
        if isinstance(item, dict)
    ]
    return AgentChatResponse(
        answer=str(result.get("answer") or ""),
        citations=citations,
    )
