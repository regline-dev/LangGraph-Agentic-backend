"""FastAPI 진입점 — /health, POST /agent/chat."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LangGraph-Agentic-backend",
    description="PDF 모드용 LangGraph Agentic API",
    version="0.1.0",
)

# 로컬 챗봇 UI(frontend_react)에서 /agent/chat 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """서버 생존·배포 헬스체크."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
