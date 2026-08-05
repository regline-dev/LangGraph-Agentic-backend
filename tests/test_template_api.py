"""PDF 템플릿 HTTP 저장 계약."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.pdf_ingest.service import PdfIngestService, get_pdf_ingest_service

client = TestClient(app)


def test_save_template_endpoint(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "app.pdf_ingest.template_store.DEFAULT_TEMPLATE_STORE_DIR",
        tmp_path,
    )
    app.dependency_overrides[get_pdf_ingest_service] = lambda: PdfIngestService()
    try:
        response = client.post(
            "/pdf/templates",
            headers={"X-Admin-User-Id": "regline"},
            json={
                "template_id": "custom_v1",
                "name": "커스텀",
                "labels": ["부서", "매출"],
                "prompt": "커스텀 지시문",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["saved"] is True
        assert body["template_id"] == "custom_v1"
        assert (tmp_path / "custom_v1.json").is_file()
        log_output = capsys.readouterr().out
        assert "api=POST /pdf/templates" in log_output
        assert "\n  admin_user_id=regline" in log_output
        assert "\n  template_id=custom_v1" in log_output
        assert "\n  result=success" in log_output
    finally:
        app.dependency_overrides.clear()


def test_save_template_failure_log_has_reason(capsys) -> None:
    app.dependency_overrides[get_pdf_ingest_service] = lambda: PdfIngestService()
    try:
        response = client.post(
            "/pdf/templates",
            headers={"X-Admin-User-Id": "regline"},
            json={
                "template_id": "invalid_v1",
                "name": "invalid",
                "labels": [],
                "prompt": "",
            },
        )
        assert response.status_code == 400
        log_output = capsys.readouterr().out
        assert "\n  result=failure" in log_output
        assert "\n  reason=" in log_output
        assert "labels" in log_output
    finally:
        app.dependency_overrides.clear()
