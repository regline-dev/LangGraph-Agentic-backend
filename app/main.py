"""FastAPI 진입점 — /health, POST /agent/chat."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.fable import router as fable_router
from app.api.ocr import router as ocr_router
from app.api.pdf_ingest import router as pdf_ingest_router
from app.config import get_settings

if sys.platform == "win32":
    from io import TextIOWrapper

    # 콘솔 기본 인코딩(cp949)이 한글 로그 print()와 충돌해 죽는 문제 방지.
    # sys.stdout 타입은 TextIO라 reconfigure가 없음. 실제 콘솔은 TextIOWrapper.
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if isinstance(sys.stderr, TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 임베딩 모델을 미리 연다.

    inspect(pymupdf) 이후에 bge-m3를 열면 Windows에서 0xC0000005로 죽는다.
    실패해도 서버는 뜨게 두고, 다음 inspect/ingest에서 다시 시도한다.
    """
    from ingest.embedder_factory import create_embedder

    try:
        create_embedder(settings)
        print(
            "[embedder_warmup] phase=startup "
            f"backend={(settings.embedding_backend or '').strip() or '-'} "
            "result=success",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            "[embedder_warmup] phase=startup result=failure\n"
            f"  reason={exc}",
            flush=True,
        )
    yield


app = FastAPI(
    title="LangGraph-Agentic-backend",
    description="PDF 모드용 LangGraph Agentic API",
    version="0.1.0",
    lifespan=lifespan,
)

# 로컬 챗봇 UI(frontend_react)에서 /agent/chat 호출 허용
# allow_origins=["*"] 와 allow_credentials=True 는 브라우저가 거부함 → credentials 끔
# (PDF Agent는 쿠키 인증 미사용. FAQ backend_python 운영 * 패턴과 동일)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # 프론트가 PDF 응답에서 우화 번호·제목을 읽도록 노출
    expose_headers=["X-Fable-Id", "X-Fable-Title", "Content-Disposition"],
)

app.include_router(agent_router)
app.include_router(fable_router)
app.include_router(ocr_router)
app.include_router(pdf_ingest_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """서버 생존·배포 헬스체크."""
    return {"status": "ok"}


if __name__ == "__main__":
    import asyncio
    import sys

    import uvicorn

    if sys.platform == "win32":
        # ProactorEventLoop는 accept 중 클라이언트가 연결을 리셋하면
        # WinError 64로 죽는 오래된 CPython 버그가 있어 Selector로 전환
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # reload=True 는 로컬 Qdrant PATH 잠금과 겹치면 워커가 옛 코드로 남을 수 있음
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
