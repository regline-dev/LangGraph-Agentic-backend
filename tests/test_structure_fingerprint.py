"""구조 지문(라벨만) 추출 — Phase 0 TDD."""

from __future__ import annotations

from pathlib import Path

from app.pdf_ingest.structure_fingerprint import (
    extract_structure_fingerprint,
    is_weak_fingerprint,
)

FIXTURE_TEXT = (
    Path(__file__).parent / "fixtures" / "fable_card_sample.txt"
).read_text(encoding="utf-8")
FABLE_TEMPLATE_LABELS = {
    "결말톤",
    "교훈 명확도",
    "내용 평가",
    "대사비중",
    "등장인물",
    "분량",
    "예상 낭독시간",
    "한마디 결론",
    "원문",
    "재미도",
    "최종평가",
    "키워드",
    "폭력성",
}


def test_fable_card_fingerprint_includes_labels_not_values() -> None:
    """이솝 카드: 재미도·원문·키워드 등 라벨은 있고, 숫자 값(2, 3, 5…)은 지문에 없다."""
    labels = extract_structure_fingerprint(
        FIXTURE_TEXT,
        known_labels=FABLE_TEMPLATE_LABELS,
    )

    for expected in ("재미도", "폭력성", "교훈 명확도", "원문", "키워드", "결말톤"):
        assert expected in labels

    # 값으로만 있는 줄은 지문에 넣지 않음
    assert "2" not in labels
    assert "3" not in labels
    assert "5" not in labels
    assert "권력남용" not in labels  # 키워드 값


def test_table_header_fingerprint() -> None:
    """표형: 파이프/탭 헤더 행에서 칸 이름만 뽑는다."""
    text = "2026년 3월 실적\n부서 | 매출 | 비용 | 인원\n영업 | 100 | 40 | 5\n"
    labels = extract_structure_fingerprint(
        text,
        known_labels=FABLE_TEMPLATE_LABELS,
    )

    assert "부서" in labels
    assert "매출" in labels
    assert "비용" in labels
    assert "인원" in labels
    assert "100" not in labels
    assert "영업" not in labels  # 데이터 행 값


def test_empty_or_plain_text_is_weak_fingerprint() -> None:
    """라벨이 거의 없으면 빈약 지문 → 이후 안 맞음 경로용."""
    assert extract_structure_fingerprint("") == frozenset()
    assert extract_structure_fingerprint("   \n  ") == frozenset()
    plain = extract_structure_fingerprint("춘향은 이몽룡과 백년가약을 맺었다.")
    assert is_weak_fingerprint(plain)


def test_fable_pdf_extract_skips_title_and_value_noise() -> None:
    """실 PDF 추출문: 제목·평가값·본문은 지문에서 빼고, 구조 라벨만 남긴다."""
    text = (
        Path(__file__).parent / "fixtures" / "fable_pdf_06_extract.txt"
    ).read_text(encoding="utf-8")
    labels = extract_structure_fingerprint(
        text,
        known_labels=FABLE_TEMPLATE_LABELS,
    )

    for expected in (
        "재미도",
        "폭력성",
        "교훈 명확도",
        "결말톤",
        "키워드",
        "원문",
        "등장인물",
        "분량",
        "최종평가",
    ):
        assert expected in labels

    # 제목·잡음·값 줄
    assert "이솝우화 #6" not in labels
    assert "아버지와 아들들" not in labels
    assert "난이도 낮음" not in labels
    assert "몰입도 보통" not in labels
    assert "일반 영상" not in labels
    assert "보통" not in labels
    assert "단결" not in labels
    assert not any("부러지고" in label for label in labels)


def test_fable_pdf_06_matches_fable_card_seed() -> None:
    """06_아버지와_아들들 추출문이 이솝 시드 템플릿과 맞음이어야 한다."""
    from app.pdf_ingest.template_match import MATCH_STATUS_MATCH, match_fingerprint_to_templates
    from app.pdf_ingest.template_store import load_templates

    text = (
        Path(__file__).parent / "fixtures" / "fable_pdf_06_extract.txt"
    ).read_text(encoding="utf-8")
    templates = [t for t in load_templates() if t.template_id == "fable_card_v1"]
    assert templates, "fable_card_v1 시드가 있어야 한다"
    labels = extract_structure_fingerprint(
        text,
        known_labels=templates[0].labels,
    )
    result = match_fingerprint_to_templates(labels, templates)
    assert result.status == MATCH_STATUS_MATCH
    assert result.prompt_locked is True
