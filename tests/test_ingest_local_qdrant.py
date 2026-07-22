"""순번 6 — 로컬 Qdrant 실적재.

1. .env 의 TEST_UPLOAD_PDF_NAME 파일을 data/uploads/ 에 둔다
2. pytest tests/test_ingest_local_qdrant.py -v -s

파일명 바꿀 때: 이 테스트가 아니라 .env 만 수정.
"""

from pathlib import Path

import pytest

from app.config import get_settings
from app.qdrant_factory import create_qdrant_client
from ingest.index_documents import DEFAULT_UPLOADS_DIR, FakeEmbedder, ingest_pdf


def test_ingest_one_pdf_from_uploads_to_local_qdrant() -> None:
    settings = get_settings()
    if not (settings.qdrant_path or "").strip():
        pytest.fail("QDRANT_PATH 를 .env 에 넣으세요")

    pdf_name = (settings.test_upload_pdf_name or "").strip()
    if not pdf_name:
        pytest.fail("TEST_UPLOAD_PDF_NAME 을 .env 에 넣으세요")

    pdf_path = DEFAULT_UPLOADS_DIR / pdf_name
    if not pdf_path.is_file():
        pytest.fail(f"이 파일을 두세요: {pdf_path}")

    client = create_qdrant_client(settings)
    try:
        indexed = ingest_pdf(
            pdf_path,
            client=client,
            collection_name=settings.qdrant_collection,
            embedder=FakeEmbedder(dimension=32),
            uploads_dir=DEFAULT_UPLOADS_DIR,
        )
        assert indexed >= 1
        storage = Path(settings.qdrant_path) / "collection" / settings.qdrant_collection
        print(f"\nOK name={pdf_name} indexed={indexed} → {storage}")
        assert storage.exists()
    finally:
        client.close()
