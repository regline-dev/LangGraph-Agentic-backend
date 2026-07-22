"""설정에 따른 Embedder 생성 — 인제스트·검색 공통."""

from __future__ import annotations

from app.config import Settings, get_settings
from ingest.bge_m3 import BgeM3Embedder
from ingest.index_documents import Embedder, FakeEmbedder

# 프로세스 내 실임베딩 모델 1회 로드
_shared_bge: BgeM3Embedder | None = None


def create_embedder(settings: Settings | None = None) -> Embedder:
    """EMBEDDING_BACKEND 에 따라 Fake 또는 bge-m3."""
    cfg = settings or get_settings()
    backend = (cfg.embedding_backend or "bge-m3").strip().lower()
    if backend in {"fake", "fakeembed", "test"}:
        return FakeEmbedder(dimension=int(cfg.fake_embed_dimension or 32))
    return _get_shared_bge(cfg.embedding_model or "BAAI/bge-m3")


def _get_shared_bge(model_name: str) -> BgeM3Embedder:
    global _shared_bge
    if _shared_bge is None or getattr(_shared_bge, "_model_name", None) != model_name:
        embedder = BgeM3Embedder(model_name=model_name)
        # 디버그용 이름 보관
        embedder._model_name = model_name  # type: ignore[attr-defined]
        _shared_bge = embedder
    return _shared_bge


def reset_shared_embedder() -> None:
    """테스트용."""
    global _shared_bge
    _shared_bge = None
