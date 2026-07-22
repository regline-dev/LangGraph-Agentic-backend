"""Agent 실행 — 도메인 분류 → 이솝 규칙 또는 ARKK holdings 검색."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qdrant_client import QdrantClient

from app.config import get_settings
from app.graph.domain_router import ClassifyFn, classify_pdf_domain
from app.graph.workflow import build_groq_agent_graph, run_agent
from app.metrics.catalog import try_handle_catalog_question, try_handle_fun_rank_question
from app.metrics.mbti_commands import try_handle_mbti_command
from app.metrics.mbti_reinterpret import reinterpret_fable_for_mbti
from app.metrics.memory import FableSessionMemory, default_fable_memory
from app.metrics.route import try_handle_metric_question
from app.metrics.title_card import try_handle_title_only_full_card
from app.metrics.vague import try_clarify_vague_question
from app.metrics.verbatim import try_handle_verbatim_body
from app.qdrant_factory import get_shared_qdrant_client
from app.tools.lookup_fable_metadata import (
    fetch_fable_body_by_title,
    list_fable_metas,
    list_fable_titles,
    lookup_fable_metadata_by_title,
)
from app.tools.search_documents import search_documents
from app.tools.search_holdings import search_holdings
from ingest.embedder_factory import create_embedder

# question [, session_id] → {answer, citations, mbti?}
AgentRunner = Callable[..., dict[str, Any]]


def create_qdrant_search_fn(
    client: QdrantClient | None = None,
) -> Callable[[str], list[dict[str, Any]]]:
    """설정값으로 우화 Qdrant 검색 함수를 만든다."""
    settings = get_settings()
    qdrant = client or get_shared_qdrant_client(settings)
    embedder = create_embedder(settings)
    collection = settings.qdrant_collection

    def search_fn(query: str) -> list[dict[str, Any]]:
        return search_documents(
            query,
            client=qdrant,
            collection_name=collection,
            embedder=embedder,
            top_k=3,
        )

    return search_fn


def create_holdings_search_fn(
    client: QdrantClient | None = None,
) -> Callable[[str], list[dict[str, Any]]]:
    """설정값으로 ARKK holdings Qdrant 검색 함수를 만든다."""
    settings = get_settings()
    qdrant = client or get_shared_qdrant_client(settings)
    embedder = create_embedder(settings)
    collection = settings.qdrant_collection_arkk

    def search_fn(query: str) -> list[dict[str, Any]]:
        return search_holdings(
            query,
            client=qdrant,
            collection_name=collection,
            embedder=embedder,
            top_k=3,
        )

    return search_fn


def _pack(
    *,
    answer: str,
    citations: list[Any] | None = None,
    mbti: str | None = None,
) -> dict[str, Any]:
    return {
        "answer": answer or "",
        "citations": list(citations or []),
        "mbti": mbti,
    }


def _run_holdings_agent(
    question: str,
    *,
    client: QdrantClient | None = None,
) -> dict[str, Any]:
    """주식지표(holdings) — 우화 규칙 없이 arkk_holdings_bge 검색 + Groq."""
    qdrant = client or get_shared_qdrant_client(get_settings())
    graph = build_groq_agent_graph(
        search_fn=create_holdings_search_fn(qdrant),
        document_domain="holdings",
    )
    state = run_agent(graph, question=question)
    return _pack(
        answer=str(state.get("answer") or ""),
        citations=state.get("citations"),
        mbti=None,
    )


def _run_fable_chat(
    question: str,
    session_id: str | None = None,
    *,
    memory: FableSessionMemory | None = None,
    client: QdrantClient | None = None,
) -> dict[str, Any]:
    """이솝 우화 — 기존 규칙 라우터 → pdf_chunks_bge Groq."""
    settings = get_settings()
    qdrant = client or get_shared_qdrant_client(settings)
    collection = settings.qdrant_collection
    session_memory = memory or default_fable_memory

    mbti_cmd = try_handle_mbti_command(
        question,
        session_id=session_id,
        memory=session_memory,
    )
    if mbti_cmd is not None:
        return _pack(
            answer=str(mbti_cmd.get("answer") or ""),
            citations=mbti_cmd.get("citations"),
            mbti=mbti_cmd.get("mbti") or session_memory.get_mbti(session_id),
        )

    try:
        known_titles = list_fable_titles(client=qdrant, collection_name=collection)
    except Exception:  # noqa: BLE001
        known_titles = []

    catalog = try_handle_catalog_question(
        question,
        list_titles_fn=lambda: known_titles,
    )
    if catalog is not None:
        return _pack(
            answer=str(catalog.get("answer") or ""),
            citations=catalog.get("citations"),
            mbti=session_memory.get_mbti(session_id),
        )

    def _list_metas() -> list[dict[str, Any]]:
        try:
            return list_fable_metas(client=qdrant, collection_name=collection)
        except Exception:  # noqa: BLE001
            return []

    fun_rank = try_handle_fun_rank_question(question, list_metas_fn=_list_metas)
    if fun_rank is not None:
        return _pack(
            answer=str(fun_rank.get("answer") or ""),
            citations=fun_rank.get("citations"),
            mbti=session_memory.get_mbti(session_id),
        )

    def fetch_body(title: str, content_type: str) -> dict[str, Any] | None:
        try:
            return fetch_fable_body_by_title(
                title,
                content_type,
                client=qdrant,
                collection_name=collection,
            )
        except Exception:  # noqa: BLE001
            return None

    def reinterpret_fn(**kwargs: Any) -> str:
        return reinterpret_fable_for_mbti(
            title=str(kwargs.get("title") or ""),
            origin_text=str(kwargs.get("origin") or ""),
            modern_text=str(kwargs.get("modern") or ""),
            mbti=str(kwargs.get("mbti") or ""),
        )

    verbatim = try_handle_verbatim_body(
        question,
        session_id=session_id,
        memory=session_memory,
        known_titles=known_titles,
        fetch_fn=fetch_body,
        reinterpret_fn=reinterpret_fn,
    )
    if verbatim is not None:
        return _pack(
            answer=str(verbatim.get("answer") or ""),
            citations=verbatim.get("citations"),
            mbti=verbatim.get("mbti") or session_memory.get_mbti(session_id),
        )

    def lookup_fn(title: str) -> dict[str, Any] | None:
        try:
            return lookup_fable_metadata_by_title(
                title,
                client=qdrant,
                collection_name=collection,
            )
        except Exception:  # noqa: BLE001
            return None

    metric = try_handle_metric_question(
        question,
        session_id=session_id,
        memory=session_memory,
        known_titles=known_titles,
        lookup_fn=lookup_fn,
    )
    if metric is not None:
        return _pack(
            answer=str(metric.get("answer") or ""),
            citations=metric.get("citations"),
            mbti=session_memory.get_mbti(session_id),
        )

    title_card = try_handle_title_only_full_card(
        question,
        session_id=session_id,
        memory=session_memory,
        known_titles=known_titles,
        lookup_fn=lookup_fn,
        fetch_fn=fetch_body,
    )
    if title_card is not None:
        return _pack(
            answer=str(title_card.get("answer") or ""),
            citations=title_card.get("citations"),
            mbti=title_card.get("mbti") or session_memory.get_mbti(session_id),
        )

    vague = try_clarify_vague_question(question, known_titles=known_titles)
    if vague is not None:
        return _pack(
            answer=str(vague.get("answer") or ""),
            citations=vague.get("citations"),
            mbti=session_memory.get_mbti(session_id),
        )

    graph = build_groq_agent_graph(
        search_fn=create_qdrant_search_fn(qdrant),
        document_domain="fable",
    )
    state = run_agent(graph, question=question)
    return _pack(
        answer=str(state.get("answer") or ""),
        citations=state.get("citations"),
        mbti=session_memory.get_mbti(session_id),
    )


def run_agent_chat(
    question: str,
    session_id: str | None = None,
    *,
    memory: FableSessionMemory | None = None,
    classify_fn: ClassifyFn | None = None,
) -> dict[str, Any]:
    """운영 경로: ② 도메인 LLM → 이솝 규칙 또는 ARKK holdings 검색."""
    domain = classify_pdf_domain(question, classify_fn=classify_fn)
    if domain == "holdings":
        return _run_holdings_agent(question)
    return _run_fable_chat(question, session_id=session_id, memory=memory)


def get_agent_runner() -> AgentRunner:
    """FastAPI Depends용 — 테스트에서 override 가능."""
    return run_agent_chat
