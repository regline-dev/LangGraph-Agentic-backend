"""벡터화 문서 버전 관리 — 문서 정체성(documents) + 버전 이력(document_versions).

판단 로직(계획: Docs/20260814_벡터화_문서버전관리_계획.md):
  document_id 있음 + 해시 다름 → 새 버전 추가(예전 버전은 is_current=0으로만 내림, 안 지움)
  document_id 없음           → 신규 삽입(버전 1)
  document_id 있음 + 해시 같음 → 처리 생략(스킵)

조회 키는 (collection, source_file) — 관리자가 문서를 직접 고르는 UI 없이 지금 업로드 흐름
그대로 두고, 판단만 파일명 대신 콘텐츠 해시로 하기 위함.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Literal

from app.pdf_ingest.template_service import _execute
from app.utils.db import get_db_connection

DocumentVersionAction = Literal["skip", "new_document", "new_version"]


def compute_content_hash(data: bytes) -> str:
    """파일 바이트 → SHA256 hex digest."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class DocumentVersionPreview:
    """1차(업로드/inspect 직후) — 조회만, 아무것도 쓰지 않는다."""

    action: DocumentVersionAction
    document_id: int | None
    next_version: int


@dataclass(frozen=True)
class DocumentVersionDecision:
    """2차(벡터화 시작 클릭) — 실제로 documents/document_versions에 쓴 결과."""

    action: DocumentVersionAction
    document_id: int
    version: int
    is_current: bool


def _find_document(cur, *, collection: str, source_file: str) -> dict | None:
    _execute(
        cur,
        "SELECT document_id_num FROM documents WHERE collection = ? AND source_file = ?",
        (collection, source_file),
        desc=f"문서 조회 (collection='{collection}', source_file='{source_file}')",
    )
    return cur.fetchone()


def _find_latest_version(cur, *, document_id_num: int) -> dict | None:
    _execute(
        cur,
        """
        SELECT version, content_hash, indexed FROM document_versions
        WHERE document_id_num = ? ORDER BY version DESC LIMIT 1
        """,
        (document_id_num,),
        desc=f"문서(id={document_id_num}) 최신 버전 조회",
    )
    return cur.fetchone()


def _indexed_count(latest: dict) -> int | None:
    raw = latest.get("indexed")
    if raw is None:
        return None
    return int(raw)


def _same_hash_should_skip(
    latest: dict,
    *,
    document_id: int,
    has_vectors: Callable[[int], bool] | None,
) -> bool:
    """해시가 같아도 벡터가 없으면 skip하지 않는다 (ingest timeout 후 재시도)."""
    indexed = _indexed_count(latest)
    if indexed is not None:
        return indexed > 0
    if has_vectors is None:
        return True
    return bool(has_vectors(document_id))


def mark_document_version_indexed(document_id: int, version: int, *, indexed: int) -> None:
    """적재 성공 후 청크 수를 버전 행에 기록한다."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        _execute(
            cur,
            """
            UPDATE document_versions
            SET indexed = ?
            WHERE document_id_num = ? AND version = ?
            """,
            (int(indexed), int(document_id), int(version)),
            desc=f"문서(id={document_id}) 버전 {version} indexed={indexed} 갱신",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def preview_document_version(
    *,
    collection: str,
    source_file: str,
    content_hash: str,
    has_vectors: Callable[[int], bool] | None = None,
) -> DocumentVersionPreview:
    """1차 판단 — 스킵/신규/새버전 예고만 하고 DB에 쓰지 않는다."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        doc = _find_document(cur, collection=collection, source_file=source_file)
        if doc is None:
            return DocumentVersionPreview(action="new_document", document_id=None, next_version=1)

        document_id_num = int(doc["document_id_num"])
        latest = _find_latest_version(cur, document_id_num=document_id_num)
        if latest is None:
            return DocumentVersionPreview(
                action="new_document", document_id=document_id_num, next_version=1
            )
        if str(latest["content_hash"]) == content_hash:
            if _same_hash_should_skip(
                latest, document_id=document_id_num, has_vectors=has_vectors
            ):
                return DocumentVersionPreview(
                    action="skip", document_id=document_id_num, next_version=int(latest["version"])
                )
            return DocumentVersionPreview(
                action="new_document",
                document_id=document_id_num,
                next_version=int(latest["version"]),
            )
        return DocumentVersionPreview(
            action="new_version",
            document_id=document_id_num,
            next_version=int(latest["version"]) + 1,
        )
    finally:
        conn.close()


def resolve_document_version(
    *,
    collection: str,
    source_file: str,
    content_hash: str,
    template_id_num: int | None = None,
    title: str | None = None,
    page_count: int | None = None,
    char_count: int | None = None,
    indexed: int | None = None,
    pdf_loader: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    has_vectors: Callable[[int], bool] | None = None,
) -> DocumentVersionDecision:
    """2차 판단 — 스킵/신규/새버전을 확정하고 실제로 documents/document_versions에 쓴다."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        doc = _find_document(cur, collection=collection, source_file=source_file)

        if doc is None:
            _execute(
                cur,
                "INSERT INTO documents (template_id_num, collection, source_file) VALUES (?, ?, ?)",
                (template_id_num, collection, source_file),
                desc=f"신규 문서 등록 (collection='{collection}', source_file='{source_file}')",
            )
            document_id_num = int(cur.lastrowid)
            latest = None
        else:
            document_id_num = int(doc["document_id_num"])
            latest = _find_latest_version(cur, document_id_num=document_id_num)

        if latest is not None and str(latest["content_hash"]) == content_hash:
            if _same_hash_should_skip(
                latest, document_id=document_id_num, has_vectors=has_vectors
            ):
                conn.commit()
                return DocumentVersionDecision(
                    action="skip",
                    document_id=document_id_num,
                    version=int(latest["version"]),
                    is_current=True,
                )
            conn.commit()
            return DocumentVersionDecision(
                action="new_document",
                document_id=document_id_num,
                version=int(latest["version"]),
                is_current=True,
            )

        next_version = int(latest["version"]) + 1 if latest is not None else 1
        indexed_value = int(indexed) if indexed is not None else 0
        if latest is not None:
            _execute(
                cur,
                "UPDATE document_versions SET is_current = 0 WHERE document_id_num = ? AND is_current = 1",
                (document_id_num,),
                desc=f"문서(id={document_id_num}) 이전 버전 is_current 해제",
            )
        _execute(
            cur,
            """
            INSERT INTO document_versions
              (document_id_num, version, content_hash, is_current, title, page_count, char_count,
               indexed, pdf_loader, chunk_size, chunk_overlap)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id_num,
                next_version,
                content_hash,
                title,
                page_count,
                char_count,
                indexed_value,
                pdf_loader,
                chunk_size,
                chunk_overlap,
            ),
            desc=f"문서(id={document_id_num}) 버전 {next_version} 기록",
        )
        conn.commit()
        return DocumentVersionDecision(
            action="new_document" if doc is None else "new_version",
            document_id=document_id_num,
            version=next_version,
            is_current=True,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
