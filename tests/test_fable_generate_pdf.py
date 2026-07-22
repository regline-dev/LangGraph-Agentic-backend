"""2차 순번 2 — POST /fable/generate-pdf HTTP 계약 테스트."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.fable_pdf.service import FableGenerateResult, get_fable_pdf_service
from app.main import app

client = TestClient(app)

# 최소 PDF 시그니처 (브라우저/뷰어가 PDF로 인식할 수준)
_FAKE_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _fake_service_ok(body_text: str, source_note: str | None = None) -> FableGenerateResult:
    """테스트용: 디스크/LLM 없이 성공 결과만 반환."""
    _ = body_text, source_note
    return FableGenerateResult(
        fable_id=42,
        title="늑대와 어린양",
        subtitle="힘 있는 자의 논리",
        pdf_bytes=_FAKE_PDF_BYTES,
    )


def _fake_service_fail(body_text: str, source_note: str | None = None) -> FableGenerateResult:
    _ = body_text, source_note
    raise RuntimeError("Groq timeout simulated")


def test_generate_pdf_rejects_empty_body() -> None:
    """빈 원문은 400 + detail."""
    app.dependency_overrides[get_fable_pdf_service] = lambda: _fake_service_ok
    try:
        response = client.post("/fable/generate-pdf", json={"body_text": "   "})
        assert response.status_code == 400
        assert "detail" in response.json()
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_returns_pdf_bytes_and_fable_id_header() -> None:
    """성공 시 PDF 바이너리 + X-Fable-Id · 제목 헤더."""
    app.dependency_overrides[get_fable_pdf_service] = lambda: _fake_service_ok
    try:
        response = client.post(
            "/fable/generate-pdf",
            json={"body_text": "옛날 어느 날 늑대가 물을 마시러 왔다."},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.headers["x-fable-id"] == "42"
        # 한글 제목은 percent-encoding (프론트에서 decodeURIComponent)
        from urllib.parse import unquote

        assert "늑대" in unquote(response.headers.get("x-fable-title", ""))
        assert response.content.startswith(b"%PDF")
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_pipeline_failure_returns_502() -> None:
    """채점/파이프라인 예외는 502 + 다시 시도 안내."""
    app.dependency_overrides[get_fable_pdf_service] = lambda: _fake_service_fail
    try:
        response = client.post(
            "/fable/generate-pdf",
            json={"body_text": "짧은 우화 원문"},
        )
        assert response.status_code == 502
        detail = response.json()["detail"]
        assert "채점" in detail or "실패" in detail
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_service_deletes_tmp_after_read(tmp_path: Path, monkeypatch) -> None:
    """서비스가 PDF를 읽은 뒤 tmp 파일을 삭제한다 (통합·서비스 단위)."""
    from app.fable_pdf import service as svc_mod

    seq_path = tmp_path / "fable_id_seq.txt"
    tmp_dir = tmp_path / "fable_pdf"
    tmp_dir.mkdir()

    def _fake_pipeline(body_text: str, fable_id: int, output_path: str, source_note: str) -> dict:
        Path(output_path).write_bytes(_FAKE_PDF_BYTES)
        return {"title": "테스트제목", "subtitle": "부제"}

    monkeypatch.setattr(svc_mod, "DEFAULT_SEQ_PATH", seq_path)
    monkeypatch.setattr(svc_mod, "DEFAULT_TMP_DIR", tmp_dir)

    result = svc_mod.generate_fable_pdf_bytes(
        "원문입니다",
        source_note=None,
        pipeline_fn=_fake_pipeline,
    )
    assert result.fable_id == 1
    assert result.pdf_bytes.startswith(b"%PDF")
    assert list(tmp_dir.glob("*.pdf")) == []
