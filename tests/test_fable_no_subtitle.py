"""부제(subtitle) 제거 — LLM 프롬프트·파이프라인·API 헤더."""

from __future__ import annotations

from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.fable_pdf.scorer import SCORE_PROMPT
from app.fable_pdf.service import FableGenerateResult, get_fable_pdf_service
from app.main import app

client = TestClient(app)

_FAKE_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_score_prompt_does_not_ask_for_subtitle() -> None:
    """LLM이 부제를 판단·생성하지 않도록 프롬프트에 subtitle 없음."""
    assert '"subtitle"' not in SCORE_PROMPT
    assert "부제" not in SCORE_PROMPT


def test_generate_pdf_response_has_no_subtitle_header() -> None:
    """성공 응답에 X-Fable-Subtitle 헤더가 없다."""

    def _fake_ok(body_text: str, source_note: str | None = None) -> FableGenerateResult:
        _ = body_text, source_note
        return FableGenerateResult(
            fable_id=1,
            title="제목만",
            pdf_bytes=_FAKE_PDF_BYTES,
        )

    app.dependency_overrides[get_fable_pdf_service] = lambda: _fake_ok
    try:
        response = client.post(
            "/fable/generate-pdf",
            json={"body_text": "짧은 우화"},
        )
        assert response.status_code == 200
        assert "x-fable-subtitle" not in {k.lower() for k in response.headers.keys()}
        assert "제목" in unquote(response.headers.get("x-fable-title", ""))
    finally:
        app.dependency_overrides.clear()
