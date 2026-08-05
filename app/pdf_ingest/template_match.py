"""구조 지문 ↔ 템플릿 비교 — 맞음 / 애매 / 안 맞음.

역할: Phase 3. Jaccard 유사도. LLM 아님.
임계 (문서화):
  - 맞음: score >= MATCH_SCORE_MIN 이고 지문이 빈약하지 않음
  - 애매: AMBIGUOUS_SCORE_MIN <= score < MATCH_SCORE_MIN
  - 안 맞음: score < AMBIGUOUS_SCORE_MIN 또는 빈약 지문 또는 템플릿 없음
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.pdf_ingest.global_labels import doc_kind_to_letter
from app.pdf_ingest.structure_fingerprint import is_weak_fingerprint
from app.pdf_ingest.template_store import PromptTemplate, has_fill_lock

logger = logging.getLogger(__name__)

MATCH_STATUS_MATCH = "match"
MATCH_STATUS_AMBIGUOUS = "ambiguous"
MATCH_STATUS_NO_MATCH = "no_match"

# 맞음 / 애매 경계
MATCH_SCORE_MIN = 0.85
AMBIGUOUS_SCORE_MIN = 0.50


@dataclass(frozen=True)
class MatchResult:
    """비교 결과."""

    status: str
    score: float = 0.0
    template: PromptTemplate | None = None
    candidates: list[PromptTemplate] = field(default_factory=list)
    prompt_locked: bool = False


def match_fingerprint_to_templates(
    fingerprint: frozenset[str],
    templates: list[PromptTemplate],
    *,
    document_kind: int | None = None,
) -> MatchResult:
    """지문과 저장 템플릿들을 비교해 맞음/애매/안맞음을 반환."""
    labels = frozenset(fingerprint or ())
    candidates = list(templates)
    # 사용자 승인 사양: A 문서는 A, C 문서는 C 템플릿하고만 비교한다.
    if document_kind is not None:
        current_doc_type = doc_kind_to_letter(document_kind)
        candidates = [
            template
            for template in candidates
            if template.doc_type == current_doc_type
        ]
    _log_inspect_summary(doc_labels=labels, templates=candidates)

    if not candidates or is_weak_fingerprint(labels):
        reason = (
            "템플릿 파일 없음"
            if not candidates
            else "구조 라벨 부족으로 템플릿 비교 생략(doc_labels 비거나 ≤2)"
        )
        _log_compare(
            doc_labels=labels,
            template=None,
            score=0.0,
            status=MATCH_STATUS_NO_MATCH,
            reason=reason,
            extra=(
                f"templates_loaded={len(candidates)} "
                f"template_ids={[t.template_id for t in candidates]}"
            ),
        )
        return MatchResult(status=MATCH_STATUS_NO_MATCH, prompt_locked=False)

    scored: list[tuple[float, PromptTemplate]] = []
    for template in candidates:
        score = _jaccard(labels, template.labels)
        scored.append((score, template))
        _log_compare(
            doc_labels=labels,
            template=template,
            score=score,
            status="candidate",
            reason="템플릿별 점수",
        )
    scored.sort(key=lambda item: item[0], reverse=True)

    best_score, best = scored[0]
    if best_score >= MATCH_SCORE_MIN:
        _log_compare(
            doc_labels=labels,
            template=best,
            score=best_score,
            status=MATCH_STATUS_MATCH,
            reason=f"score>={MATCH_SCORE_MIN}",
        )
        return MatchResult(
            status=MATCH_STATUS_MATCH,
            score=best_score,
            template=best,
            candidates=[best],
            # 결과 양식 또는 레거시 지시문이 있을 때만 잠금 (판별만 되면 탐색 가능)
            prompt_locked=has_fill_lock(best),
        )

    if best_score >= AMBIGUOUS_SCORE_MIN:
        candidates = [
            template
            for score, template in scored
            if score >= AMBIGUOUS_SCORE_MIN
        ]
        _log_compare(
            doc_labels=labels,
            template=best,
            score=best_score,
            status=MATCH_STATUS_AMBIGUOUS,
            reason=f"{AMBIGUOUS_SCORE_MIN}<=score<{MATCH_SCORE_MIN}",
        )
        return MatchResult(
            status=MATCH_STATUS_AMBIGUOUS,
            score=best_score,
            template=None,
            candidates=candidates,
            prompt_locked=False,
        )

    _log_compare(
        doc_labels=labels,
        template=best,
        score=best_score,
        status=MATCH_STATUS_NO_MATCH,
        reason=f"score<{AMBIGUOUS_SCORE_MIN}",
    )
    return MatchResult(
        status=MATCH_STATUS_NO_MATCH,
        score=best_score,
        template=None,
        candidates=[],
        prompt_locked=False,
    )


def _log_inspect_summary(
    *,
    doc_labels: frozenset[str],
    templates: list[PromptTemplate],
) -> None:
    """inspect 진입 시 한눈에 보는 요약."""
    lines = [
        f"[template_match] --- inspect 요약 ---",
        f"  doc_labels({len(doc_labels)})={sorted(doc_labels)}",
        f"  templates_loaded={len(templates)}",
    ]
    for tpl in templates:
        lines.append(
            f"  · id={tpl.template_id} labels={sorted(tpl.labels)} "
            f"has_schema={bool(tpl.result_schema)}"
        )
    message = "\n".join(lines)
    print(message, flush=True)
    _append_match_log(message)


def _append_match_log(message: str) -> None:
    from pathlib import Path

    log_path = Path(__file__).resolve().parents[2] / "logs" / "template_match.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass


def _log_compare(
    *,
    doc_labels: frozenset[str],
    template: PromptTemplate | None,
    score: float,
    status: str,
    reason: str,
    extra: str = "",
) -> None:
    """매칭 단어(라벨) 비교 로그 (콘솔 + UTF-8 파일)."""
    doc_sorted = sorted(doc_labels)
    if template is None:
        message = (
            f"[template_match] status={status} reason={reason} "
            f"doc_labels={doc_sorted}"
        )
        if extra:
            message += f" {extra}"
    else:
        seed = template.labels
        inter = sorted(doc_labels & seed)
        only_doc = sorted(doc_labels - seed)
        only_seed = sorted(seed - doc_labels)
        message = (
            f"[template_match] status={status} reason={reason} "
            f"template_id={template.template_id} score={score:.4f}\n"
            f"  교집합={inter}\n"
            f"  문서에만={only_doc}\n"
            f"  시드에만={only_seed}\n"
            f"  doc_labels={doc_sorted}\n"
            f"  seed_labels={sorted(seed)}"
        )
        if extra:
            message += f"\n  {extra}"

    logger.info(message)
    print(message, flush=True)
    _append_match_log(message)

def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)
