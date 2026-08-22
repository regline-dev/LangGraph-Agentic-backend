"""템플릿 비교 Phase 3 TDD — 맞음 / 애매 / 안 맞음."""

from __future__ import annotations

from app.pdf_ingest.template_match import (
    MATCH_STATUS_AMBIGUOUS,
    MATCH_STATUS_MATCH,
    MATCH_STATUS_NO_MATCH,
    MatchResult,
    match_filename_to_templates,
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


def test_compare_ignores_whitespace_but_stored_labels_keep_it() -> None:
    """doc_match_labels(template.labels)는 원문 그대로(공백 유지) 저장되지만,
    Jaccard 비교 직전엔 양쪽 다 공백을 제거해서 미세한 공백 차이로 억울하게
    안 겹치는 걸 막는다(Docs/20260812 계획)."""
    templates = [
        PromptTemplate(
            template_id="aesop",
            name="AESOP",
            labels=frozenset({"결말톤", "내용 평가", "키워드", "영상화 적합도", "한마디 결론"}),
            prompt="",
            result_schema={"METADATA_NAME": "AESOP"},
        )
    ]
    # 공백 형태가 살짝 다른 문서(추출기 차이 등)여도 정규화 후엔 완전히 겹침
    fingerprint = frozenset({"결말톤", "내용평가", "키워드", "영상화적합도", "한마디결론"})

    result = match_fingerprint_to_templates(fingerprint, templates)

    assert result.status == MATCH_STATUS_MATCH
    assert result.template is not None
    assert result.template.template_id == "aesop"


def test_document_kind_excludes_templates_without_doc_type() -> None:
    """DOC_TYPE 없는 레거시 템플릿을 A/C 후보에 섞지 않는다."""
    templates = [_tpl("legacy", "제목", "작성자", "발행일")]

    result = match_fingerprint_to_templates(
        frozenset({"제목", "작성자", "발행일"}),
        templates,
        document_kind=1,
    )

    assert result.status == MATCH_STATUS_NO_MATCH


def _tpl_with_metadata_name(template_id: str, metadata_name: str, *, doc_type: str = "A") -> PromptTemplate:
    return PromptTemplate(
        template_id=template_id,
        name=template_id,
        labels=frozenset(),
        prompt="",
        result_schema={"METADATA_NAME": metadata_name},
        doc_type=doc_type,
    )


def test_filename_match_single_candidate() -> None:
    """파일명에 등록 템플릿명이 포함되고 후보가 하나면 맞음."""
    templates = [_tpl_with_metadata_name("aesop", "AESOP")]

    result = match_filename_to_templates("AESOP_헤라클레스와 마부.pdf", templates)

    assert result.status == MATCH_STATUS_MATCH
    assert result.template is not None
    assert result.template.template_id == "aesop"


def test_filename_match_is_case_insensitive() -> None:
    templates = [_tpl_with_metadata_name("aesop", "AESOP")]

    result = match_filename_to_templates("aesop_test.pdf", templates)

    assert result.status == MATCH_STATUS_MATCH


def test_filename_no_keyword_is_no_match() -> None:
    templates = [_tpl_with_metadata_name("aesop", "AESOP")]

    result = match_filename_to_templates("random_document.pdf", templates)

    assert result.status == MATCH_STATUS_NO_MATCH
    assert result.template is None


def test_filename_matches_multiple_candidates_is_no_match() -> None:
    """여러 템플릿명이 동시에 파일명에 걸리면(애매) 자동 선택 안 함 — ④로 넘어감."""
    templates = [
        _tpl_with_metadata_name("ark", "ARK"),
        _tpl_with_metadata_name("arkk", "ARKK"),
    ]

    result = match_filename_to_templates("ARKK_report.pdf", templates)

    assert result.status == MATCH_STATUS_NO_MATCH


def test_filename_match_respects_document_kind() -> None:
    templates = [_tpl_with_metadata_name("aesop_c", "AESOP", doc_type="C")]

    result = match_filename_to_templates(
        "AESOP_문서.pdf", templates, document_kind=1
    )

    assert result.status == MATCH_STATUS_NO_MATCH
