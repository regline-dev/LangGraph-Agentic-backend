"""구조 지문 — 일반 추출 규칙으로 PDF 라벨 이름만 추출한다."""

from __future__ import annotations

from typing import Iterable

from app.pdf_ingest.metadata_extract import extract_structure_labels

# 이 개수 미만이면 빈약 지문 (안 맞음/애매 쪽으로)
WEAK_FINGERPRINT_MAX_LABELS = 2

def extract_structure_fingerprint(
    text: str,
    *,
    known_labels: Iterable[str] = (),
) -> frozenset[str]:
    """텍스트에서 값이 아닌 라벨 집합을 반환한다."""
    return extract_structure_labels(text, known_labels=known_labels)


def is_weak_fingerprint(labels: Iterable[str]) -> bool:
    """라벨이 너무 적어 템플릿 매칭에 쓰기 어려운지."""
    return len(frozenset(labels)) <= WEAK_FINGERPRINT_MAX_LABELS
