"""document_version — content_hash 계산 + 문서ID/버전 판단 (Hetzner 터널 DB, 안 되면 skip).

계획: Docs/20260814_벡터화_문서버전관리_계획.md
"""

from __future__ import annotations

import uuid

import mariadb
import pytest

from app.pdf_ingest.document_version import (
    compute_content_hash,
    preview_document_version,
    resolve_document_version,
    mark_document_version_indexed,
)
from app.utils.db import get_db_connection


def test_compute_content_hash_same_bytes_same_hash() -> None:
    assert compute_content_hash(b"hello") == compute_content_hash(b"hello")


def test_compute_content_hash_different_bytes_different_hash() -> None:
    assert compute_content_hash(b"hello") != compute_content_hash(b"world")


def test_compute_content_hash_is_sha256_hex() -> None:
    # sha256(b"") 의 잘 알려진 값
    assert compute_content_hash(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@pytest.fixture(scope="module")
def db_ready():
    try:
        conn = get_db_connection()
        conn.close()
    except mariadb.Error as exc:
        pytest.skip(f"MariaDB 연결 불가: {exc}")


def _unique_source_file() -> str:
    return f"doc_{uuid.uuid4().hex[:10]}.pdf"


def _cleanup(collection: str, source_file: str) -> None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM documents WHERE collection = ? AND source_file = ?",
            (collection, source_file),
        )
        conn.commit()
    finally:
        conn.close()


def test_preview_new_file_is_new_document(db_ready) -> None:
    source_file = _unique_source_file()
    try:
        preview = preview_document_version(
            collection="test_collection", source_file=source_file, content_hash="abc"
        )
        assert preview.action == "new_document"
        assert preview.document_id is None
        assert preview.next_version == 1
    finally:
        _cleanup("test_collection", source_file)


def test_resolve_new_file_inserts_version_1(db_ready) -> None:
    source_file = _unique_source_file()
    try:
        decision = resolve_document_version(
            collection="test_collection",
            source_file=source_file,
            content_hash="hash-a",
            title="제목",
            page_count=3,
        )
        assert decision.action == "new_document"
        assert decision.version == 1
        assert decision.is_current is True
    finally:
        _cleanup("test_collection", source_file)


def test_resolve_same_hash_again_skips(db_ready) -> None:
    source_file = _unique_source_file()
    try:
        first = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )
        mark_document_version_indexed(first.document_id, first.version, indexed=3)
        second = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )
        assert second.action == "skip"
        assert second.document_id == first.document_id
        assert second.version == 1
    finally:
        _cleanup("test_collection", source_file)


def test_resolve_same_hash_without_vectors_retries(db_ready) -> None:
    """Qdrant 실패 후 indexed=0 이면 같은 내용도 skip하지 않는다."""
    source_file = _unique_source_file()
    try:
        first = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )
        preview = preview_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )
        assert preview.action == "new_document"
        second = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )
        assert second.action == "new_document"
        assert second.document_id == first.document_id
        assert second.version == first.version
    finally:
        _cleanup("test_collection", source_file)


def test_preview_null_indexed_without_vectors_does_not_skip(db_ready) -> None:
    """예전 행(indexed NULL)은 벡터가 없을 때만 재적재."""
    source_file = _unique_source_file()
    try:
        first = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE document_versions SET indexed = NULL WHERE document_id_num = ?",
                (first.document_id,),
            )
            conn.commit()
        finally:
            conn.close()
        preview = preview_document_version(
            collection="test_collection",
            source_file=source_file,
            content_hash="hash-a",
            has_vectors=lambda _document_id: False,
        )
        assert preview.action == "new_document"
        preview_ok = preview_document_version(
            collection="test_collection",
            source_file=source_file,
            content_hash="hash-a",
            has_vectors=lambda _document_id: True,
        )
        assert preview_ok.action == "skip"
    finally:
        _cleanup("test_collection", source_file)


def test_resolve_changed_hash_adds_new_version_and_preview_matches(db_ready) -> None:
    source_file = _unique_source_file()
    try:
        first = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-a"
        )

        preview = preview_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-b"
        )
        assert preview.action == "new_version"
        assert preview.document_id == first.document_id
        assert preview.next_version == 2

        second = resolve_document_version(
            collection="test_collection", source_file=source_file, content_hash="hash-b"
        )
        assert second.action == "new_version"
        assert second.document_id == first.document_id
        assert second.version == 2
        assert second.is_current is True

        conn = get_db_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT version, is_current FROM document_versions WHERE document_id_num = ? ORDER BY version",
                (first.document_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        assert [r["version"] for r in rows] == [1, 2]
        assert [bool(r["is_current"]) for r in rows] == [False, True]
    finally:
        _cleanup("test_collection", source_file)
