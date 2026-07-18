"""환경변수 로딩 — 서버·Groq·Vector Store."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """앱 설정 (.env 또는 환경변수)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8005

    # Groq (검색 판단 LLM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Vector Store — Chroma처럼 로컬 PATH 우선, 비면 HOST:PORT(Docker)
    qdrant_path: str = ""
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "pdf_chunks"


def get_settings() -> Settings:
    """설정 싱글톤 — 테스트·런타임에서 동일 규약 사용."""
    return Settings()
