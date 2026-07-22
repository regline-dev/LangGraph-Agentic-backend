"""ARKK holdings PDF → arkk_holdings_bge 인제스트 CLI.

사용:
  1. LangGraph/Docs/ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf 를 data/uploads/ 에 복사
  2. python scripts/ingest_arkk_holdings.py

로컬 QDRANT_PATH 사용 시 에이전트 서버를 잠시 끄고 실행할 것.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 import path에 추가
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import get_settings
from app.qdrant_factory import get_shared_qdrant_client, reset_shared_qdrant_client
from ingest.embedder_factory import create_embedder, reset_shared_embedder
from ingest.holdings_metadata import DEFAULT_MANIFEST_PATH, load_arkk_manifest
from ingest.index_documents import DEFAULT_UPLOADS_DIR
from ingest.ingest_arkk import ingest_arkk_from_manifest


def main() -> None:
    settings = get_settings()
    entry = load_arkk_manifest()
    pdf_path = DEFAULT_UPLOADS_DIR / entry["path"]
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"PDF 없음: {pdf_path}\n"
            f"LangGraph/Docs/{entry['path']} 를 data/uploads/ 에 복사하세요."
        )

    reset_shared_embedder()
    embedder = create_embedder(settings)
    print(
        f"embedder={type(embedder).__name__} dim={embedder.dimension} "
        f"collection={settings.qdrant_collection_arkk}"
    )

    reset_shared_qdrant_client()
    client = get_shared_qdrant_client(settings)
    try:
        indexed = ingest_arkk_from_manifest(
            client=client,
            collection_name=settings.qdrant_collection_arkk,
            embedder=embedder,
        )
        count = client.count(collection_name=settings.qdrant_collection_arkk).count
        print(f"OK manifest={DEFAULT_MANIFEST_PATH.name} indexed={indexed} total={count}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
