"""template_service CRUD (Hetzner 터널 DB) — DB 연결 안 되면 skip."""

from __future__ import annotations

import uuid

import mariadb
import pytest

from app.pdf_ingest.template_service import load_templates, save_template, soft_delete_template
from app.pdf_ingest.template_store import PromptTemplate
from app.utils.db import get_db_connection


@pytest.fixture(scope="module")
def db_ready():
    try:
        conn = get_db_connection()
        conn.close()
    except mariadb.Error as exc:
        pytest.skip(f"MariaDB 연결 불가: {exc}")


def _unique_id() -> str:
    return f"t_{uuid.uuid4().hex[:10]}"


def test_save_and_load_roundtrip(db_ready) -> None:
    tid = _unique_id()
    save_template(
        PromptTemplate(
            template_id=tid,
            name="테스트 템플릿",
            labels=frozenset({"부서", "매출"}),
            result_schema={
                "DOC_TYPE": "C",
                "METADATA_NAME": tid.upper(),
                "DESCRIPTION": "테스트용",
                "dept": "영업1팀",
                "search_labels": {"dept": "부서"},
            },
            doc_type="C",
        )
    )
    try:
        loaded = {t.template_id: t for t in load_templates()}
        assert tid in loaded
        template = loaded[tid]
        assert template.name == "테스트 템플릿"
        assert template.labels == frozenset({"부서", "매출"})
        assert template.result_schema["METADATA_NAME"] == tid.upper()
        assert template.result_schema["dept"] == "영업1팀"
        assert template.result_schema["search_labels"]["dept"] == "부서"
    finally:
        soft_delete_template(tid)


def test_save_stamps_creator_and_updater_from_schema(db_ready) -> None:
    """result_schema의 template_created_by/template_updated_by가 DB에 그대로 저장·복원돼야 함 —
    하드코딩된 'system' 회귀 방지."""
    tid = _unique_id()
    save_template(
        PromptTemplate(
            template_id=tid,
            name="감사필드 테스트",
            labels=frozenset({"라벨"}),
            result_schema={
                "DOC_TYPE": "C",
                "METADATA_NAME": tid.upper(),
                "template_created_by": "alice",
                "template_updated_by": "alice",
            },
            doc_type="C",
        )
    )
    try:
        loaded = {t.template_id: t for t in load_templates()}
        schema = loaded[tid].result_schema
        assert schema["template_created_by"] == "alice"
        assert schema["template_updated_by"] == "alice"
        assert schema["template_created_at"]
        assert schema["template_updated_at"]
    finally:
        soft_delete_template(tid)


def test_save_update_changes_updater_but_not_creator(db_ready) -> None:
    """수정 시 template_updated_by만 새 로그인 id로 바뀌고, created_by/created_at은 최초 등록값 유지."""
    tid = _unique_id()
    save_template(
        PromptTemplate(
            template_id=tid,
            name="최초",
            labels=frozenset({"라벨"}),
            result_schema={
                "DOC_TYPE": "C",
                "METADATA_NAME": tid.upper(),
                "template_created_by": "alice",
                "template_updated_by": "alice",
            },
            doc_type="C",
        )
    )
    first = {t.template_id: t for t in load_templates()}[tid].result_schema

    save_template(
        PromptTemplate(
            template_id=tid,
            name="수정",
            labels=frozenset({"라벨"}),
            result_schema={
                "DOC_TYPE": "C",
                "METADATA_NAME": tid.upper(),
                "template_created_by": first["template_created_by"],
                "template_updated_by": "bob",
            },
            doc_type="C",
        )
    )
    try:
        second = {t.template_id: t for t in load_templates()}[tid].result_schema
        assert second["template_created_by"] == "alice"
        assert second["template_created_at"] == first["template_created_at"]
        assert second["template_updated_by"] == "bob"
    finally:
        soft_delete_template(tid)


def test_save_upserts_existing_template(db_ready) -> None:
    tid = _unique_id()
    save_template(
        PromptTemplate(
            template_id=tid,
            name="초기명",
            labels=frozenset({"라벨1"}),
            prompt="초기 지시문",
        )
    )
    save_template(
        PromptTemplate(
            template_id=tid,
            name="수정명",
            labels=frozenset({"라벨2"}),
            prompt="수정 지시문",
        )
    )
    try:
        loaded = {t.template_id: t for t in load_templates()}
        template = loaded[tid]
        assert template.name == "수정명"
        # doc_match_labels(라벨)는 최초 등록 시에만 캡처 — 수정해도 안 바뀜(Docs/20260812 계획)
        assert template.labels == frozenset({"라벨1"})
        assert template.prompt == "수정 지시문"
    finally:
        soft_delete_template(tid)


def test_soft_delete_excludes_from_load(db_ready) -> None:
    tid = _unique_id()
    save_template(
        PromptTemplate(
            template_id=tid,
            name="삭제될 템플릿",
            labels=frozenset({"라벨"}),
            prompt="지시문",
        )
    )
    soft_delete_template(tid)
    loaded_ids = {t.template_id for t in load_templates()}
    assert tid not in loaded_ids


def test_soft_delete_missing_template_raises(db_ready) -> None:
    with pytest.raises(FileNotFoundError):
        soft_delete_template(f"missing_{uuid.uuid4().hex[:8]}")


def test_save_allows_empty_labels(db_ready) -> None:
    """구조 라벨이 하나도 없는 문서(예: +ADD로만 필드 정의)도 등록 가능해야 함 —
    doc_match_labels가 비어도 저장은 허용(③ 매칭만 안 될 뿐)."""
    tid = _unique_id()
    save_template(
        PromptTemplate(
            template_id=tid,
            name="라벨 없음",
            labels=frozenset(),
            prompt="지시문",
        )
    )
    try:
        loaded = {t.template_id: t for t in load_templates()}
        assert loaded[tid].labels == frozenset()
    finally:
        soft_delete_template(tid)
