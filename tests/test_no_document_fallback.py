"""PDF 문서 없음 → LLM 금지 / 히트 시 가공 ON·OFF."""

from app.graph.no_document_fallback import (
    apply_hit_answer_policy,
    build_no_document_response,
    format_citation_snippets,
)


def test_no_document_never_calls_llm() -> None:
    called = False

    def fake_llm(_question: str) -> str:
        nonlocal called
        called = True
        return "호출되면 안 됨"

    result = build_no_document_response(
        "커피 종류는",
        fallback_enabled=True,
        llm_invoke=fake_llm,
    )

    assert result == {"answer": "학습 데이터가 없습니다.", "citations": []}
    assert called is False


def test_hit_polish_on_keeps_llm_answer() -> None:
    cites = [{"source_file": "a.pdf", "page": 1, "snippet": "예산은 계획이다"}]
    result = apply_hit_answer_policy(
        answer="예산은 수입과 지출을 미리 잡는 계획입니다.",
        citations=cites,
        polish_enabled=True,
    )
    assert "수입과 지출" in result["answer"]
    assert result["citations"] == cites


def test_hit_polish_off_uses_snippets_only() -> None:
    cites = [{"source_file": "a.pdf", "page": 1, "snippet": "예산은 계획이다"}]
    result = apply_hit_answer_policy(
        answer="LLM이 꾸민 문장",
        citations=cites,
        polish_enabled=False,
    )
    assert "관련 문서 발췌" in result["answer"]
    assert "예산은 계획이다" in result["answer"]
    assert "꾸민 문장" not in result["answer"]


def test_format_citation_snippets_empty() -> None:
    assert format_citation_snippets([]) == "학습 데이터가 없습니다."
