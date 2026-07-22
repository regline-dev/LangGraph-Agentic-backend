"""BAAI/bge-m3 실임베딩 — 인제스트·검색 공통."""

from __future__ import annotations

from typing import Any

# bge-m3 dense 출력 차원 (공식)
BGE_M3_DIMENSION = 1024


class BgeM3Embedder:
    """SentenceTransformer(BAAI/bge-m3) 래퍼. 모델은 생성 시에만 로드."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        *,
        model: Any | None = None,
    ) -> None:
        if model is not None:
            self._model = model
        else:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    "sentence-transformers가 필요합니다. "
                    'pip install "sentence-transformers" 후 다시 시도하세요.'
                ) from exc
            # 첫 실행 시 Hugging Face에서 모델 다운로드
            self._model = SentenceTransformer(model_name)
        dim = self._model.get_sentence_embedding_dimension()
        self.dimension = int(dim)
        if self.dimension <= 0:
            raise ValueError("임베딩 차원이 올바르지 않습니다.")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        raw = self._model.encode(texts, normalize_embeddings=True)
        if hasattr(raw, "tolist"):
            vectors = raw.tolist()
        else:
            vectors = [list(row) for row in raw]
        return [[float(x) for x in row] for row in vectors]
