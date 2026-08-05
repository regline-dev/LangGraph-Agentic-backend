"""템플릿 비교 Phase 3 TDD — 맞음 / 애매 / 안 맞음."""

from __future__ import annotations

from app.pdf_ingest.template_match import (
    MATCH_STATUS_AMBIGUOUS,
    MATCH_STATUS_MATCH,
    MATCH_STATUS_NO_MATCH,
    MatchResult,
    match_fingerprint_to_templates,
)
from app.pdf_ingest.template_store import PromptTemplate


def _tpl(template_id: str, *labels: str, doc_type: str | None = None) -> PromptTemplate:
    return PromptTemplate(
        template_id=template_id,
        name=template_id,
        labels=frozenset(labels),
        prompt=f"prompt for {template_id}",
        doc_type=doc_type,
    )


def test_exact_overlap_is_match() -> None:
    """지문과 템플릿 라벨이 같으면 맞음 · (레거시 prompt 있으면) 잠금."""
    templates = [_tpl("a", "재미도", "원문", "키워드", "폭력성")]
    fingerprint = frozenset({"재미도", "원문", "키워드", "폭력성"})

    result = match_fingerprint_to_templates(fingerprint, templates)

    assert result.status == MATCH_STATUS_MATCH
    assert result.template is not None
    assert result.template.template_id == "a"
    assert result.prompt_locked is True
    assert result.score >= 0.85


def test_match_without_result_schema_or_prompt_is_unlocked() -> None:
    """판별만 되고 결과 양식·지시문 없으면 잠금 안 함(탐색 가능)."""
    templates = [
        PromptTemplate(
            template_id="label_only",
            name="라벨만",
            labels=frozenset({"재미도", "원문", "키워드", "폭력성"}),
            prompt="",
            result_schema=None,
        )
    ]
    fingerprint = frozenset({"재미도", "원문", "키워드", "폭력성"})
    result = match_fingerprint_to_templates(fingerprint, templates)
    assert result.status == MATCH_STATUS_MATCH
    assert result.prompt_locked is False


def test_match_with_result_schema_locks() -> None:
    templates = [
        PromptTemplate(
            template_id="with_schema",
            name="양식있음",
            labels=frozenset({"재미도", "원문", "키워드", "폭력성"}),
            prompt="",
            result_schema={"재미도": 0, "원문": ""},
        )
    ]
    fingerprint = frozenset({"재미도", "원문", "키워드", "폭력성"})
    result = match_fingerprint_to_templates(fingerprint, templates)
    assert result.status == MATCH_STATUS_MATCH
    assert result.prompt_locked is True


def test_weak_fingerprint_is_no_match(capsys) -> None:
    """라벨이 너무 적으면 안 맞음 (이후 LLM 추천)."""
    templates = [_tpl("a", "재미도", "원문", "키워드", "폭력성")]
    fingerprint = frozenset({"재미도"})

    result = match_fingerprint_to_templates(fingerprint, templates)
    console_output = capsys.readouterr().out

    assert result.status == MATCH_STATUS_NO_MATCH
    assert result.prompt_locked is False
    assert result.template is None
    assert "구조 라벨 부족으로 템플릿 비교 생략" in console_output
    assert "이솝" not in console_output
    assert "ARKK" not in console_output


def test_partial_overlap_is_ambiguous() -> None:
    """일부만 겹치면 애매 · 후보 템플릿 목록."""
    templates = [
        _tpl("fable", "재미도", "원문", "키워드", "폭력성", "교훈 명확도"),
        _tpl("holdings", "부서", "매출", "비용", "인원"),
    ]
    # 이솝 라벨 중 절반 정도만
    fingerprint = frozenset({"재미도", "원문", "키워드"})

    result = match_fingerprint_to_templates(fingerprint, templates)

    assert result.status == MATCH_STATUS_AMBIGUOUS
    assert result.prompt_locked is False
    assert result.candidates
    assert result.candidates[0].template_id == "fable"


def test_no_templates_is_no_match() -> None:
    result = match_fingerprint_to_templates(frozenset({"부서", "매출"}), [])
    assert result.status == MATCH_STATUS_NO_MATCH
    assert isinstance(result, MatchResult)


def test_unrelated_labels_is_no_match() -> None:
    templates = [_tpl("fable", "재미도", "원문", "키워드", "폭력성")]
    fingerprint = frozenset({"부서", "매출", "비용", "인원"})

    result = match_fingerprint_to_templates(fingerprint, templates)

    assert result.status == MATCH_STATUS_NO_MATCH
    assert result.prompt_locked is False


def test_document_kind_compares_only_same_doc_type_templates() -> None:
    """A/C 라벨이 같아도 현재 문서 종류의 템플릿만 후보가 된다."""
    shared_labels = ("제목", "작성자", "발행일")
    templates = [
        _tpl("general", *shared_labels, doc_type="A"),
        _tpl("table", *shared_labels, doc_type="C"),
    ]

    result = match_fingerprint_to_templates(
        frozenset(shared_labels),
        templates,
        document_kind=1,
    )

    assert result.status == MATCH_STATUS_MATCH
    assert result.template is not None
    assert result.template.template_id == "general"


def test_document_kind_excludes_templates_without_doc_type() -> None:
    """DOC_TYPE 없는 레거시 템플릿을 A/C 후보에 섞지 않는다."""
    templates = [_tpl("legacy", "제목", "작성자", "발행일")]

    result = match_fingerprint_to_templates(
        frozenset({"제목", "작성자", "발행일"}),
        templates,
        document_kind=1,
    )

    assert result.status == MATCH_STATUS_NO_MATCH
