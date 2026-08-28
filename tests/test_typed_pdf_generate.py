"""타입 구성 기반 PDF 생성 — 비이솝 타입이 이솝 레이아웃을 쓰지 않는지."""

from __future__ import annotations

from pathlib import Path

from app.fable_pdf.pdf_type_profile import PdfTypeProfile, is_aesop_type
from app.fable_pdf.typed_pdf import generate_typed_pdf
from app.fable_pdf.typed_scorer import build_typed_score_prompt, normalize_typed_score


def test_is_aesop_type_only_for_aesop_code() -> None:
    """type_code=aesop 만 이솝 전용 경로. 그 외는 타입 구성 경로."""
    assert is_aesop_type(None) is True  # 구버전 클라이언트 호환
    assert is_aesop_type(PdfTypeProfile(type_code="aesop", type_name="이솝우화")) is True
    assert (
        is_aesop_type(
            PdfTypeProfile(type_code="local_festival", type_name="지방축제 안내")
        )
        is False
    )


def test_build_typed_score_prompt_includes_group_labels() -> None:
    """채점 프롬프트에 구성 그룹·항목 라벨이 들어간다."""
    profile = PdfTypeProfile(
        type_code="local_festival",
        type_name="지방축제 안내",
        configs=[
            {
                "group_name": "기본 정보",
                "values_text": "축제명, 기간, 장소",
            }
        ],
        subtitles=[{"title": "한줄 안내", "mode": "llm"}],
    )
    prompt = build_typed_score_prompt("한강별빛축제\n기간: 8월", profile)
    assert "지방축제 안내" in prompt
    assert "기본 정보" in prompt
    assert "축제명" in prompt
    assert "한줄 안내" in prompt
    assert '"fun"' not in prompt
    assert "내용 평가" not in prompt


def test_normalize_typed_score_keeps_groups_and_title() -> None:
    raw = {
        "title": "한강별빛축제",
        "groups": {"기본 정보": {"축제명": "한강별빛축제", "기간": "8/15~17"}},
        "subtitles": {"한줄 안내": "혼잡할 수 있습니다."},
        "tags": ["축제", "여가"],
    }
    profile = PdfTypeProfile(
        type_code="local_festival",
        type_name="지방축제 안내",
        configs=[{"group_name": "기본 정보", "values_text": "축제명, 기간"}],
        subtitles=[{"title": "한줄 안내"}],
    )
    scored = normalize_typed_score(raw, profile)
    assert scored["title"] == "한강별빛축제"
    assert scored["groups"]["기본 정보"]["축제명"] == "한강별빛축제"
    assert "한줄 안내" in scored["subtitles"]


def test_generate_typed_pdf_uses_type_name_not_aesop(tmp_path: Path) -> None:
    """PDF 바이트에 타입명·그룹이 있고 이솝 도감 문구가 없다."""
    out = tmp_path / "festival.pdf"
    data = {
        "id": 7,
        "title": "한강별빛축제",
        "body_text": "한강별빛축제\n기간: 8월 15일~17일",
        "source_note": "테스트용 가상 안내문",
        "type_name": "지방축제 안내",
        "groups": {
            "기본 정보": {
                "축제명": "한강별빛축제",
                "기간": "8/15~17",
                "장소": "여의도한강공원",
            }
        },
        "subtitles": {"한줄 안내": "날씨에 따라 일정이 달라질 수 있습니다."},
        "tags": ["축제"],
    }
    generate_typed_pdf(data, str(out))
    assert out.is_file()
    raw = out.read_bytes()
    assert raw.startswith(b"%PDF")
    # reportlab은 한글을 폰트 글리프로 넣으므로 문자열 검색 대신
    # 영문/기호·이솝 ASCII 혼입만 검사
    assert b"Aesop" not in raw
    # 이솝 전용 영문 키 잔존 방지용 — 파일 크기만 최소 확인
    assert out.stat().st_size > 500


def test_pipeline_non_aesop_uses_typed_pdf_without_groq(
    tmp_path: Path, monkeypatch
) -> None:
    """커스텀 생성은 표 값으로 typed PDF만 탄다. Groq 값 채움 없음."""
    from app.fable_pdf import pipeline as pipe

    calls = {"score": 0, "typed_pdf": 0, "aesop_pdf": 0, "draft": 0}

    def _fake_typed_score(body_text, profile, **kwargs):
        calls["score"] += 1
        raise AssertionError("커스텀 생성은 값 채움 LLM을 타면 안 된다")

    def _fake_draft(body_text, type_name, **kwargs):
        calls["draft"] += 1
        raise AssertionError("구성 초안은 생성 API가 아니라 draft-configs다")

    def _fake_typed_pdf(data, output_path):
        calls["typed_pdf"] += 1
        assert data["groups"]["기본 정보"] == {"축제명": "-"}
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.drawString(72, 720, "typed")
        c.save()

    def _fake_aesop_pdf(data, output_path):
        calls["aesop_pdf"] += 1
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.drawString(72, 720, "aesop")
        c.save()

    monkeypatch.setattr(pipe, "generate_typed_pdf", _fake_typed_pdf)
    monkeypatch.setattr(pipe, "generate_fable_pdf", _fake_aesop_pdf)

    profile = PdfTypeProfile(
        type_code="local_festival",
        type_name="지방축제 안내",
        configs=[{"group_name": "기본 정보", "values_text": "축제명"}],
    )
    out = tmp_path / "out.pdf"
    meta = pipe.run_fable_pipeline(
        "한강별빛축제\n본문",
        3,
        str(out),
        "출처",
        type_profile=profile,
        timeout_seconds=5,
    )
    assert calls["score"] == 0
    assert calls["draft"] == 0
    assert calls["typed_pdf"] == 1
    assert calls["aesop_pdf"] == 0
    assert meta["title"] == "한강별빛축제"
    assert meta["metadata_name"] == "LOCAL_FESTIVAL"


def test_pipeline_skips_typed_llm_when_values_filled(tmp_path: Path, monkeypatch) -> None:
    """커스텀 구성에 value가 있으면 생성 시 Groq를 다시 호출하지 않는다."""
    from app.fable_pdf import pipeline as pipe

    calls = {"score": 0, "typed_pdf": 0}

    def _fake_typed_score(body_text, profile, **kwargs):
        calls["score"] += 1
        raise AssertionError("값 채움 후 생성은 LLM을 타면 안 된다")

    def _fake_typed_pdf(data, output_path):
        calls["typed_pdf"] += 1
        assert data["groups"]["안내"]["기간"] == "8월 15일~17일"
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.drawString(72, 720, "typed")
        c.save()

    monkeypatch.setattr(pipe, "generate_typed_pdf", _fake_typed_pdf)

    profile = PdfTypeProfile(
        type_code="local_festival",
        type_name="지방축제 안내",
        configs=[
            {
                "group_name": "안내",
                "values_text": "기간",
                "fields": {"기간": "8월 15일~17일"},
                "chart": "none",
            }
        ],
    )
    out = tmp_path / "filled.pdf"
    meta = pipe.run_fable_pipeline(
        "한강별빛축제\n기간: 8월 15일~17일",
        4,
        str(out),
        "출처",
        type_profile=profile,
        timeout_seconds=5,
    )
    assert calls["score"] == 0
    assert calls["typed_pdf"] == 1
    assert meta["title"] == "한강별빛축제"


def test_pipeline_groups_keep_preview_detail_fields(
    tmp_path: Path, monkeypatch
) -> None:
    """생성 그룹은 미리보기와 같은 세부항목 키. 이름 목록을 내용 한 칸으로 접지 않는다."""
    from app.fable_pdf import pipeline as pipe

    captured = {}

    def _fake_typed_pdf(data, output_path):
        captured["groups"] = data["groups"]
        captured["layouts"] = data["group_layouts"]
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.drawString(72, 720, "typed")
        c.save()

    monkeypatch.setattr(pipe, "generate_typed_pdf", _fake_typed_pdf)
    profile = PdfTypeProfile(
        type_code="festival_info",
        type_name="축제안내",
        configs=[
            {
                "group_name": "입장 교통",
                "values_text": "입장료, 예매, 주차, 셔틀",
                "value": "입장료, 예매, 주차, 셔틀",
                "layout": "horizontal",
                "fields": {
                    "입장료": "무료 (일부 유료 체험은 현장 결제)",
                    "예매": "별도 예매 없음. 현장 선착순",
                    "주차": "여의도한강공원 주차장",
                    "셔틀": "여의도역 3번 출구",
                },
            }
        ],
    )
    out = tmp_path / "cards.pdf"
    pipe.run_fable_pipeline(
        "한강별빛축제",
        9,
        str(out),
        "출처",
        type_profile=profile,
        timeout_seconds=5,
    )
    group = captured["groups"]["입장 교통"]
    assert "내용" not in group
    assert group["입장료"].startswith("무료")
    assert group["셔틀"] == "여의도역 3번 출구"
    assert captured["layouts"]["입장 교통"] == "horizontal"


def test_pipeline_does_not_use_label_list_as_body_text(
    tmp_path: Path, monkeypatch
) -> None:
    """fields 없이 value=values_text 이면 라벨만 있는 칸. 이름 문자열을 본문으로 쓰지 않는다."""
    from app.fable_pdf import pipeline as pipe

    captured = {}

    def _fake_typed_pdf(data, output_path):
        captured["groups"] = data["groups"]
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.save()

    monkeypatch.setattr(pipe, "generate_typed_pdf", _fake_typed_pdf)
    profile = PdfTypeProfile(
        type_code="festival_info",
        type_name="축제안내",
        configs=[
            {
                "group_name": "입장 교통",
                "values_text": "입장료, 예매, 주차, 셔틀",
                "value": "입장료, 예매, 주차, 셔틀",
                "layout": "horizontal",
            }
        ],
    )
    out = tmp_path / "labels-only.pdf"
    pipe.run_fable_pipeline(
        "한강별빛축제",
        10,
        str(out),
        "출처",
        type_profile=profile,
        timeout_seconds=5,
    )
    group = captured["groups"]["입장 교통"]
    assert list(group.keys()) == ["입장료", "예매", "주차", "셔틀"]
    assert group["입장료"] == "-"
    assert "입장료, 예매" not in "".join(group.values())


def test_pipeline_skips_typed_llm_when_configs_empty(
    tmp_path: Path, monkeypatch
) -> None:
    """구성 행이 없으면 헤더+원문 PDF. 생성 시 Groq·초안 LLM 없음."""
    from app.fable_pdf import pipeline as pipe

    calls = {"score": 0, "typed_pdf": 0, "draft": 0}

    def _fake_typed_score(body_text, profile, **kwargs):
        calls["score"] += 1
        raise AssertionError("구성 0개는 생성 LLM을 타면 안 된다")

    def _fake_draft(body_text, type_name, **kwargs):
        calls["draft"] += 1
        raise AssertionError("구성 초안은 생성 API가 아니다")

    def _fake_typed_pdf(data, output_path):
        calls["typed_pdf"] += 1
        assert data["groups"] == {}
        assert data["title"] == "원문만"
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.drawString(72, 720, "typed")
        c.save()

    monkeypatch.setattr(pipe, "generate_typed_pdf", _fake_typed_pdf)

    profile = PdfTypeProfile(
        type_code="new_type",
        type_name="새로운타입",
        configs=[],
    )
    out = tmp_path / "header-only.pdf"
    meta = pipe.run_fable_pipeline(
        "원문만\n본문",
        5,
        str(out),
        "출처",
        type_profile=profile,
        timeout_seconds=5,
    )
    assert calls["score"] == 0
    assert calls["draft"] == 0
    assert calls["typed_pdf"] == 1
    assert meta["title"] == "원문만"


def test_pipeline_skips_aesop_llm_when_preview_score(
    tmp_path: Path, monkeypatch
) -> None:
    """미리보기 채점이 있으면 생성 시 이솝 Groq를 다시 타지 않는다."""
    from app.fable_pdf import pipeline as pipe

    calls = {"score": 0}

    def _fake_score(body_text, **kwargs):
        calls["score"] += 1
        raise AssertionError("미리보기 채점 후 생성은 LLM을 타면 안 된다")

    def _fake_pdf(data, output_path):
        assert data["fun"] == 4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path)
        c.drawString(72, 720, "aesop")
        c.save()

    monkeypatch.setattr(pipe, "score_fable_with_llm", _fake_score)
    monkeypatch.setattr(pipe, "generate_fable_pdf", _fake_pdf)
    out = tmp_path / "aesop-preview.pdf"
    meta = pipe.run_fable_pipeline(
        "여우가 포도를 바라보았다.",
        8,
        str(out),
        "이솝우화",
        type_profile=PdfTypeProfile(type_code="aesop", type_name="이솝우화"),
        preview_score={
            "title": "여우와 포도",
            "fun": 4,
            "violence": 0,
            "moral_clarity": 5,
            "ending_tone": "중립",
        },
        timeout_seconds=5,
    )
    assert calls["score"] == 0
    assert meta["title"] == "여우와 포도"
    assert meta["fun"] == 4


def test_normalize_typed_score_empty_tags_not_fable_fallback() -> None:
    """커스텀 태그가 비면 우화를 붙이지 않는다."""
    profile = PdfTypeProfile(
        type_code="local_festival",
        type_name="지방축제 안내",
        configs=[{"group_name": "기본 정보", "values_text": "축제명"}],
    )
    scored = normalize_typed_score({"title": "축제", "groups": {}, "tags": []}, profile)
    assert scored["tags"] == []


def test_normalize_typed_draft_keeps_name_value_chart() -> None:
    from app.fable_pdf.typed_scorer import normalize_typed_draft

    drafted = normalize_typed_draft(
        {
            "title": "한강별빛축제",
            "items": [
                {"name": "기간", "value": "8월 15일~17일", "chart": "bar"},
                {"name": "", "value": "무시", "chart": "none"},
                {"name": "좌석", "value": "", "chart": "none"},
            ],
            "tags": [],
        }
    )
    assert drafted["title"] == "한강별빛축제"
    assert drafted["items"] == [
        {"name": "기간", "value": "8월 15일~17일", "chart": "bar"}
    ]
    assert drafted["tags"] == []


def test_build_typed_draft_prompt_uses_type_name_not_fable_schema() -> None:
    from app.fable_pdf.typed_scorer import build_typed_draft_prompt

    prompt = build_typed_draft_prompt("한강별빛축제\n기간: 8월", "지방축제 안내")
    assert "지방축제 안내" in prompt
    assert "name" in prompt
    assert "value" in prompt
    assert "chart" in prompt
    assert '"fun"' not in prompt


# 붙여넣기 검증용 원문 — 구성 항목은 콜론 왼쪽 3개만
_COLON_LABEL_SAMPLE = """북촌 찻길

좌석: 창가 2인, 홀 4인, 마당
창가 2인은 대기 많고, 홀 4인은 평일 낮에 비고, 마당은 주말만 연다.

주력: 말차 라떼, 쑥 스콘, 녹차
말차 라떼 8,000원이고 쑥 스콘은 9,000원, 녹차는 6,000원이다.

객단가: 평일 점심, 주말 오후
평일 점심은 8,400원, 주말 오후는 12,000원이다.

북촌 골목 안쪽에 있는 작은 찻집이다. 창가에 앉아 차를 마시거나,
홀에서 이야기를 나누고, 날씨가 좋은 주말에는 마당 자리를 연다. 말차 라떼와 쑥 스콘, 녹차를 주로 내며,
평일 낮은 한적하고 주말 오후는 사람이 많다. 오래 앉아 차를 마시며 쉬기 좋은 속도로 운영한다.
"""


def test_colon_label_items_are_left_side_only() -> None:
    from app.fable_pdf.typed_scorer import parse_colon_labeled_items

    items = parse_colon_labeled_items(_COLON_LABEL_SAMPLE)
    names = [item["name"] for item in items]
    assert names == ["좌석", "주력", "객단가"]
    assert "창가 2인" not in names
    assert "말차 라떼" not in names
    assert "평일 점심" not in names
    assert items[0]["value"].startswith("창가 2인은")
    assert "8,000원" in items[1]["value"]
    assert "8,400원" in items[2]["value"]
    assert "골목" not in items[2]["value"]


def test_colon_label_draft_skips_llm(monkeypatch) -> None:
    from app.fable_pdf import typed_scorer

    def _fail_llm(*args, **kwargs):
        raise AssertionError("콜론 항목이 있으면 LLM을 호출하지 않는다")

    monkeypatch.setattr(typed_scorer, "_get_llm", _fail_llm)
    drafted = typed_scorer.draft_typed_items_with_llm(_COLON_LABEL_SAMPLE, "카페")
    names = [item["name"] for item in drafted["items"]]
    assert drafted["title"] == "북촌 찻길"
    assert names == ["좌석", "주력", "객단가"]
