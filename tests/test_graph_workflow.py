"""Phase 1 — LangGraph Tool 0회 / 1회 시나리오."""

from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from app.graph.workflow import MAX_TOOL_CALLS, build_agent_graph, run_agent
from app.tools.search_documents import search_documents
from ingest.index_documents import FakeEmbedder, ingest_pdf, store_upload
from tests.fixtures_helper import ensure_sample_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_tool_zero_times_skips_search_and_returns_answer() -> None:
    """검색이 필요 없으면 Tool을 호출하지 않고 최종 답변만 낸다."""
    tool_calls: list[str] = []

    def decide_no_search(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "need_search": False,
            "search_query": "",
            "answer": "검색이 필요 없는 질문입니다. 저는 PDF 문서 검색을 돕습니다.",
        }

    def fake_search(query: str) -> list[dict[str, Any]]:
        tool_calls.append(query)
        return []

    graph = build_agent_graph(decide_fn=decide_no_search, search_fn=fake_search)
    result = run_agent(graph, question="너는 누구야?")

    assert result["tool_call_count"] == 0
    assert tool_calls == []
    assert result["answer"]
    assert "검색" in result["answer"] or "PDF" in result["answer"]
    assert result["citations"] == []


def test_tool_one_time_searches_then_answers(tmp_path: Path) -> None:
    """문서 질문 → 검색 1회 → Observation으로 답변."""
    uploads = tmp_path / "uploads"
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder(dimension=32)
    saved = store_upload(ensure_sample_pdf(FIXTURES_DIR), uploads_dir=uploads)
    ingest_pdf(
        saved,
        client=client,
        collection_name="pdf_chunks",
        embedder=embedder,
        uploads_dir=uploads,
    )

    tool_calls: list[str] = []

    def decide_then_answer(state: dict[str, Any]) -> dict[str, Any]:
        # 이미 검색 결과가 있으면 답변
        observations = state.get("observations") or []
        if observations:
            texts = " ".join(str(item.get("page_content", "")) for item in observations)
            return {
                "need_search": False,
                "search_query": "",
                "answer": f"문서 근거: {texts[:120]}",
            }
        # 첫 판단: 검색 필요
        return {
            "need_search": True,
            "search_query": "annual leave",
            "answer": "",
        }

    def search_fn(query: str) -> list[dict[str, Any]]:
        tool_calls.append(query)
        return search_documents(
            query,
            client=client,
            collection_name="pdf_chunks",
            embedder=embedder,
            top_k=3,
        )

    graph = build_agent_graph(decide_fn=decide_then_answer, search_fn=search_fn)
    result = run_agent(graph, question="연차는 며칠인가요?")

    assert len(tool_calls) == 1
    assert result["tool_call_count"] == 1
    assert result["answer"]
    assert "leave" in result["answer"].lower() or "fifteen" in result["answer"].lower() or "문서" in result["answer"]
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["source_file"] == "sample.pdf"
    assert "score" in result["citations"][0]
    assert isinstance(result["citations"][0]["score"], float)


def test_tool_call_cap_stops_infinite_search() -> None:
    """판단이 계속 검색을 요청해도 상한에서 final로 간다."""
    tool_calls: list[str] = []

    def always_search(_state: dict[str, Any]) -> dict[str, Any]:
        return {"need_search": True, "search_query": "x", "answer": ""}

    def fake_search(query: str) -> list[dict[str, Any]]:
        tool_calls.append(query)
        return [
            {
                "page_content": "hit",
                "metadata": {"source_file": "a.pdf", "page": 1, "chunk_id": "a-001"},
                "score": 0.9,
            }
        ]

    graph = build_agent_graph(decide_fn=always_search, search_fn=fake_search)
    result = run_agent(graph, question="무한 검색?")

    assert len(tool_calls) == MAX_TOOL_CALLS
    assert result["tool_call_count"] == MAX_TOOL_CALLS


def test_tool_two_times_researches_then_answers() -> None:
    """1차 검색 부족 → 재검색(2회) → 종합 답변."""
    tool_calls: list[str] = []

    def decide_with_research(state: dict[str, Any]) -> dict[str, Any]:
        count = int(state.get("tool_call_count") or 0)
        observations = state.get("observations") or []

        if count == 0:
            return {
                "need_search": True,
                "search_query": "leave policy",
                "answer": "",
            }
        if count == 1:
            # 1차 결과로는 부족하다고 보고 재검색
            return {
                "need_search": True,
                "search_query": "fifteen days annual",
                "answer": "",
            }
        texts = " ".join(str(item.get("page_content", "")) for item in observations)
        return {
            "need_search": False,
            "search_query": "",
            "answer": f"종합 답변(검색 {count}회): {texts[:160]}",
        }

    def fake_search(query: str) -> list[dict[str, Any]]:
        tool_calls.append(query)
        return [
            {
                "page_content": f"snippet for {query}",
                "metadata": {
                    "source_file": "sample.pdf",
                    "page": 1,
                    "chunk_id": f"sample-{len(tool_calls):03d}",
                },
                "score": 0.8,
            }
        ]

    graph = build_agent_graph(decide_fn=decide_with_research, search_fn=fake_search)
    result = run_agent(graph, question="연차와 휴가 규정을 자세히 알려줘")

    assert len(tool_calls) == 2
    assert tool_calls[0] == "leave policy"
    assert tool_calls[1] == "fifteen days annual"
    assert result["tool_call_count"] == 2
    assert "종합" in result["answer"] or "검색 2회" in result["answer"]
    assert len(result["citations"]) >= 2
    assert result["citations"][0]["source_file"] == "sample.pdf"
