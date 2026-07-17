"""FastAPI 진입점 — Phase 0: /health, 이후 /agent/chat 확장."""

from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LangGraph-Agentic-backend",
    description="PDF 모드용 LangGraph Agentic API",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """서버 생존·배포 헬스체크."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
