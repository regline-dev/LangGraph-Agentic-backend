"""순번 22 — Dockerfile / .dockerignore 계약."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_dockerignore_exists_and_excludes_tests_and_secrets() -> None:
    path = ROOT / ".dockerignore"
    assert path.is_file(), ".dockerignore 가 있어야 한다"
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    # 이미지에 넣지 않을 항목
    assert "tests" in lowered
    assert ".env" in lowered
    assert ".venv" in lowered or "venv" in lowered
    assert "data/uploads" in lowered or "uploads" in lowered


def test_dockerfile_exists_and_ships_app_ingest_on_8010() -> None:
    path = ROOT / "Dockerfile"
    assert path.is_file(), "Dockerfile 이 있어야 한다"
    text = path.read_text(encoding="utf-8")
    assert "python:3.11" in text.lower() or "python:3.11-slim" in text
    assert "COPY app" in text or "COPY ./app" in text
    assert "COPY ingest" in text or "COPY ./ingest" in text
    assert "8010" in text
    assert "uvicorn" in text.lower()
    assert "app.main:app" in text
    # tests 를 이미지에 복사하지 않는다
    assert "COPY tests" not in text
    assert "COPY ./tests" not in text
