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
        # session_id는 지표 질문 단기 메모리용 (선택)
        result = runner(question, body.session_id)
    except TypeError:
        # 테스트용 fake runner가 session_id를 안 받는 경우
        result = runner(question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — API 경계에서 안내
        raise HTTPException(
            status_code=502,
            detail=f"Agent 실행 실패: {exc}",
        ) from exc

    citations_raw = result.get("citations") or []
    citations: list[Citation] = []
    for item in citations_raw:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        citations.append(
            Citation(
                source_file=str(item.get("source_file", "")),
                page=int(item.get("page") or 0),
                snippet=str(item.get("snippet", "")),
                score=score,
            )
        )
    # 응답 단위 유사도 = citation score 최댓값 (검색 안 탄 규칙은 0)
    top_similarity = max((c.score for c in citations), default=0.0)
    if result.get("similarity") is not None:
        try:
            top_similarity = max(top_similarity, float(result["similarity"]))
        except (TypeError, ValueError):
            pass
    mbti_raw = result.get("mbti")
    mbti = str(mbti_raw).strip().upper() if mbti_raw else None
    return AgentChatResponse(
        answer=str(result.get("answer") or ""),
        citations=citations,
        mbti=mbti or None,
        similarity=top_similarity,
    )
