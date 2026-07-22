"""테스트용 3편: 컬렉션 차원 맞춘 뒤 uploads에서 bge-m3 재인제스트.

주의: 로컬 QDRANT_PATH 사용 시 에이전트 서버를 잠시 끄고 실행할 것.
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.qdrant_factory import get_shared_qdrant_client, reset_shared_qdrant_client
from ingest.embedder_factory import create_embedder, reset_shared_embedder
from ingest.fable_parse import parse_fable_card
from ingest.index_documents import DEFAULT_UPLOADS_DIR, ingest_pdf
from ingest.load_pdf import load_pdf_pages

TARGET_NAMES = [
    "01_늑대와 어린양.pdf",
    "02_박쥐와_족제비.pdf",
    "06_아버지와_아들들.pdf",
]


def _delete_by_source(client, collection: str, source_file: str) -> None:
    existing = {item.name for item in client.get_collections().collections}
    if collection not in existing:
        print(f"  (no collection, skip delete) {collection}")
        return
    client.delete(
        collection_name=collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="source_file",
                        match=qmodels.MatchValue(value=source_file),
                    )
                ]
            )
        ),
    )
    print(f"  deleted filter source_file={source_file}")


def main() -> None:
    settings = get_settings()
    uploads = DEFAULT_UPLOADS_DIR
    reset_shared_embedder()
    embedder = create_embedder(settings)
    print(f"embedder={type(embedder).__name__} dim={embedder.dimension} backend={settings.embedding_backend}")

    client = get_shared_qdrant_client(settings)
    collection = settings.qdrant_collection

    # FakeEmbed(32) → bge-m3(1024) 전환 시 컬렉션 통째로 재생성
    existing = {item.name for item in client.get_collections().collections}
    if collection in existing:
        print(f"recreate collection {collection} for dim={embedder.dimension}")
        client.delete_collection(collection)

    for name in TARGET_NAMES:
        path = uploads / name
        if not path.exists():
            raise FileNotFoundError(f"PDF 없음: {path}")

        pages = load_pdf_pages(path)
        text = "\n".join(page.text for page in pages)
        parsed = parse_fable_card(text)
        if parsed is None:
            raise RuntimeError(f"우화 카드 파싱 실패: {name}")
        if not (parsed.get("modern_text") or "").strip():
            raise RuntimeError(f"modern_text 비어 있음: {name}")
        print(f"OK parse {name} title={parsed['title']!r}")

        # 컬렉션을 통째로 지운 뒤에는 개별 삭제 불필요
        if collection in {item.name for item in client.get_collections().collections}:
            _delete_by_source(client, collection, name)
        count = ingest_pdf(
            path,
            client=client,
            collection_name=collection,
            embedder=embedder,
            uploads_dir=uploads,
        )
        print(f"  ingested {count} chunks ← {name}")

    reset_shared_qdrant_client()
    print("done")


if __name__ == "__main__":
    main()
