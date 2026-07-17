"""환경변수 로딩 — Phase 0에서는 서버 호스트·포트만 사용."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """앱 설정 (.env 또는 환경변수)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8005


def get_settings() -> Settings:
    """설정 싱글톤 — 테스트·런타임에서 동일 규약 사용."""
    return Settings()
