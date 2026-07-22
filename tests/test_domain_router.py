"""Phase D — PDF 도메인 라우터 (이솝 vs ARKK) TDD."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from qdrant_client import QdrantClient

from app.graph.domain_router import (
    classify_pdf_domain,
    classify_pdf_domain_heuristic,
    parse_domain_json,
)
from app.graph.runtime import run_agent_chat
from app.tools.search_holdings import search_holdings
from ingest.chunk import chunk_pages
from ingest.holdings_metadata import apply_metadata_to_chunks, validate_manifest_entry
from ingest.index_documents import FakeEmbedder, index_chunks
from ingest.ingest_arkk import ingest_arkk_pdf
from ingest.load_pdf import PdfPage
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_domain_json_accepts_fable_and_holdings() -> None:
    assert parse_domain_json('{"domain": "holdings"}') == "holdings"
    assert parse_domain_json('{"domain": "fable"}') == "fable"


def test_classify_heuristic_arkk_is_holdings() -> None:
    assert classify_pdf_domain_heuristic("ARKK 1위 종목 비중은?") == "holdings"
    assert classify_pdf_domain_heuristic("테슬라 ETF 보유 비중") == "holdings"


def test_classify_heuristic_fable_is_fable() -> None:
    assert classify_pdf_domain_heuristic("늑대와 어린양 재미도") == "fable"
    assert classify_pdf_domain_heuristic("전체 목록") == "fable"


def test_classify_pdf_domain_uses_injected_fn() -> None:
    assert (
        classify_pdf_domain("아무 질문", classify_fn=lambda _q: "holdings")
        == "holdings"
    )


def test_search_holdings_includes_fund_metadata() -> None:
    """holdings 검색 결과 metadata에 fund·as_of_date가 포함된다."""
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    pages = [
        PdfPage(
            text="Tesla Inc 12.5% weight in ARKK",
            source_file="ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
            page=1,
        ),
    ]
    chunks = chunk_pages(pages, chunk_size=200, chunk_overlap=20)
    entry = validate_manifest_entry(
        {
            "path": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
            "as_of_date": "2025-11-26",
            "fund": "ARKK",
        }
    )
    stamped = apply_metadata_to_chunks(
        chunks, entry, source_file="ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf"
    )
    index_chunks(
        stamped,
        client=client,
        collection_name="arkk_test",
        embedder=embedder,
    )

    hits = search_holdings(
        "Tesla weight",
        client=client,
        collection_name="arkk_test",
        embedder=embedder,
        top_k=1,
    )
    assert hits
    meta = hits[0]["metadata"]
    assert meta.get("fund") == "ARKK"
    assert meta.get("as_of_date") == "2025-11-26"


def test_holdings_route_skips_fable_catalog() -> None:
    """holdings 도메인이면 우화 catalog 규칙을 타지 않는다."""
    catalog_called: list[str] = []

    def fake_catalog(question: str, **kwargs: Any) -> dict[str, Any] | None:
        catalog_called.append(question)
        return {"answer": "우화 목록", "citations": []}

    def fake_holdings_agent(question: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "answer": f"holdings:{question}",
            "citations": [
                {
                    "source_file": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf",
                    "page": 1,
                    "snippet": "Tesla",
                    "score": 0.9,
                }
            ],
        }

    with patch("app.graph.runtime.try_handle_catalog_question", fake_catalog):
        with patch("app.graph.runtime._run_holdings_agent", fake_holdings_agent):
            result = run_agent_chat(
                "ARKK 종목 비중",
                classify_fn=lambda _q: "holdings",
            )

    assert catalog_called == []
    assert result["answer"].startswith("holdings:")
    assert result["citations"][0]["source_file"] == "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf"


def test_fable_route_still_hits_catalog() -> None:
    """fable 도메인이면 기존 catalog 규칙이 동작한다."""
    mem_client = QdrantClient(":memory:")
    with patch("app.graph.runtime.get_shared_qdrant_client", return_value=mem_client):
        with patch("app.graph.runtime.list_fable_titles", return_value=[]):
            with patch(
                "app.graph.runtime.try_handle_catalog_question",
                lambda q, **kw: {"answer": "목록 OK", "citations": []},
            ):
                result = run_agent_chat(
                    "전체 목록",
                    classify_fn=lambda _q: "fable",
                )

    assert "목록" in result["answer"]


def test_holdings_agent_graph_with_fake_search(tmp_path: Path) -> None:
    """holdings 경로 — 검색 fn이 arkk 컬렉션 결과를 citations로 반환."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    source = ensure_sample_pdf(FIXTURES_DIR)
    saved = uploads / "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf"
    saved.write_bytes(source.read_bytes())

    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    entry = validate_manifest_entry(
        {
            "path": saved.name,
            "as_of_date": "2025-11-26",
            "fund": "ARKK",
            "chunk_size": 40,
            "chunk_overlap": 10,
        }
    )
    ingest_arkk_pdf(
        saved,
        client=client,
        collection_name="arkk_holdings_test",
        embedder=embedder,
        manifest_entry=entry,
        uploads_dir=uploads,
    )

    def decide_search(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("observations"):
            obs = state["observations"][0]
            return {
                "need_search": False,
                "search_query": "",
                "answer": f"found:{obs.get('metadata', {}).get('fund')}",
            }
        return {"need_search": True, "search_query": "leave", "answer": ""}

    def search_fn(query: str) -> list[dict[str, Any]]:
        return search_holdings(
            query,
            client=client,
            collection_name="arkk_holdings_test",
            embedder=embedder,
            top_k=1,
        )

    from app.graph.workflow import build_agent_graph, run_agent

    graph = build_agent_graph(decide_fn=decide_search, search_fn=search_fn)
    state = run_agent(graph, question="ARKK holdings")

    assert state["tool_call_count"] == 1
    assert state["citations"]
    assert state["citations"][0]["source_file"] == "ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf"
