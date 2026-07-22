"""환경변수 로딩 — 서버·Groq·Vector Store."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """앱 설정 (.env 또는 환경변수)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8010

    # Groq (검색 판단 LLM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Vector Store — Chroma처럼 로컬 PATH 우선, 비면 HOST:PORT(Docker)
    qdrant_path: str = ""
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    # bge-m3(1024)용 — FakeEmbed(32) 시절 pdf_chunks 와 분리
    qdrant_collection: str = "pdf_chunks_bge"
    # ARKK holdings — 우화 컬렉션과 분리
    qdrant_collection_arkk: str = "arkk_holdings_bge"

    # 순번 6 로컬 인제스트 테스트용 — data/uploads/ 안 파일명
    test_upload_pdf_name: str = "01_늑대와 어린양.pdf"

    # 임베딩 — 운영 기본 bge-m3, 단위테스트는 fake 주입
    # embedding_backend: "bge-m3" | "fake"
    embedding_backend: str = "bge-m3"
    embedding_model: str = "BAAI/bge-m3"
    fake_embed_dimension: int = 32


def get_settings() -> Settings:
    """설정 싱글톤 — 테스트·런타임에서 동일 규약 사용."""
    return Settings()
