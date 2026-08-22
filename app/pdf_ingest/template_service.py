"""템플릿 등록 DB 접근 — template_registry/template_labels/template_fields.

template_store.py(JSON)와 같은 함수 시그니처(save_template/load_templates/
soft_delete_template)의 DB 버전. PromptTemplate 모양은 그대로 재사용한다.

고정 키(GLOBAL_LABELS) 24개 중 DOC_TYPE·METADATA_NAME·DESCRIPTION만 템플릿
소속이라 template_registry 컬럼으로 저장한다. 나머지(문서/벡터화마다 생기는
값)는 이 설계 범위 밖 — Docs/20260810_템플릿등록_DB_ERD.md 부록 참고.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.pdf_ingest.global_labels import SEARCH_LABELS_KEY, global_label_keys, normalize_result_schema
from app.pdf_ingest.template_store import PromptTemplate
from app.utils.db import _get_caller_info, get_db_connection


def _sql_literal(value: Any) -> str:
    """디버그 로그 전용 — 값을 SQL 리터럴 표기로 바꾼다 (실행에는 안 씀, 항상 파라미터 바인딩으로 실행)."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _resolve_sql_for_log(sql: str, params: tuple) -> str:
    """? 자리에 파라미터 값을 채운 SQL — 로그에서 바로 읽고 복붙 테스트할 수 있게."""
    resolved = sql
    for value in params:
        resolved = resolved.replace("?", _sql_literal(value), 1)
    return resolved


def _execute(cur, sql: str, params: tuple = (), *, desc: str) -> None:
    """cur.execute 대신 이걸 써서 쿼리를 로그로 남긴다.
    desc: 이 쿼리가 뭘 확인/처리하려는 건지 사람이 읽을 목적 설명(필수) — admin_backend_python의
    pdf_type_service.py와 같은 형식(전역 로깅 규칙: DB 쿼리 로그는 DEBUG_ONOFF와 무관하게 항상 찍음).
    """
    file_name, _func_name = _get_caller_info()
    resolved_sql = (_resolve_sql_for_log(sql, params) if params else sql).rstrip()
    print(f"[DB 쿼리] {file_name} / {desc} <<< {resolved_sql}")
    if params:
        print(f"[DB 쿼리] 파라미터: {params!r}")

    cur.execute(sql, params)

    if sql.strip().upper().startswith("SELECT"):
        rowcount = cur.rowcount
        print(f"[DB 쿼리] 조회 결과: {rowcount if rowcount is not None and rowcount >= 0 else '?'}건")
    else:
        print(f"[DB 쿼리] 실행 완료 (lastrowid: {cur.lastrowid})")
    print()


def _variable_fields_from_schema(schema: dict[str, Any]) -> list[tuple[str, str, str]]:
    """result_schema에서 고정 키·search_labels를 뺀 가변 필드만 (key, korean_label, value)."""
    fixed_keys = set(global_label_keys())
    search_labels = schema.get(SEARCH_LABELS_KEY)
    labels_map = search_labels if isinstance(search_labels, dict) else {}
    fields: list[tuple[str, str, str]] = []
    for key, value in schema.items():
        if key in fixed_keys or key == SEARCH_LABELS_KEY:
            continue
        korean = str(labels_map.get(key, "")).strip()
        fields.append((str(key), korean, "" if value is None else str(value)))
    return fields


def _resolve_audit_login(
    schema: dict[str, Any] | None, key: str, *, fallback: str = "system"
) -> str:
    """result_schema에서 template_created_by/template_updated_by 값을 읽는다 — 없으면/빈값이면 fallback."""
    raw = schema.get(key) if schema else None
    value = str(raw).strip() if raw is not None else ""
    return value or fallback


def _format_audit_timestamp(value: Any) -> str:
    """created_at/updated_at(DB TIMESTAMP) → ISO 8601 문자열.
    mariadb 커넥터는 TIMESTAMP 컬럼을 naive datetime.datetime으로 반환한다.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def save_template(template: PromptTemplate) -> None:
    """템플릿을 upsert — template_code 있으면 갱신, 없으면 신규 등록.

    doc_match_labels(구조 라벨 매칭용, template.labels)는 최초 등록(INSERT) 시에만
    캡처해서 저장한다 — "수정"(UPDATE)해도 안 건드림(Docs/20260812 계획 결정사항).
    등록 당시 문서에 구조 라벨이 하나도 없을 수 있어(예: +ADD로만 필드 정의) 비어 있어도 허용.
    """
    template_id = (template.template_id or "").strip()
    if not template_id:
        raise ValueError("template_id가 비어 있습니다.")

    prompt_text = (template.prompt or "").strip()
    schema = template.result_schema if isinstance(template.result_schema, dict) else None
    if schema is not None and len(schema) == 0:
        schema = None
    if schema is None and not prompt_text:
        raise ValueError("결과 양식(result_schema) 또는 탐색 지시문(prompt)이 필요합니다.")

    metadata_name = str(schema.get("METADATA_NAME") or "").strip() if schema else ""
    doc_type = (template.doc_type or (schema.get("DOC_TYPE") if schema else None) or "").strip() or None
    description = str(schema.get("DESCRIPTION") or "") if schema else ""

    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        _execute(
            cur,
            "SELECT template_id_num FROM template_registry WHERE template_code = ?",
            (template_id,),
            desc=f"template_code='{template_id}' 존재 확인(upsert 분기)",
        )
        row = cur.fetchone()
        if row:
            tid_num = int(row["template_id_num"])
            updated_by = _resolve_audit_login(schema, "template_updated_by")
            _execute(
                cur,
                """
                UPDATE template_registry
                SET template_name = ?, metadata_name = ?, doc_type = ?, prompt = ?, is_active = 1,
                    updated_by = ?, updated_at = CURRENT_TIMESTAMP()
                WHERE template_id_num = ?
                """,
                (template.name or template_id, metadata_name or None, doc_type, prompt_text, updated_by, tid_num),
                desc=f"템플릿 갱신 (template_code='{template_id}') — doc_match_labels·created_by/created_at는 안 건드림",
            )
        else:
            doc_match_labels = ",".join(sorted(template.labels)) if template.labels else None
            created_by = _resolve_audit_login(schema, "template_created_by")
            updated_by = _resolve_audit_login(schema, "template_updated_by")
            _execute(
                cur,
                """
                INSERT INTO template_registry
                  (template_code, template_name, metadata_name, doc_type, prompt, doc_match_labels, is_active, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    template_id,
                    template.name or template_id,
                    metadata_name or None,
                    doc_type,
                    prompt_text,
                    doc_match_labels,
                    created_by,
                    updated_by,
                ),
                desc=f"신규 템플릿 등록 (template_code='{template_id}')",
            )
            tid_num = int(cur.lastrowid)

        _execute(
            cur,
            "DELETE FROM template_fields WHERE template_id_num = ?",
            (tid_num,),
            desc=f"템플릿(id={tid_num}) 기존 가변 필드 삭제(재저장 전)",
        )
        if schema:
            for index, (key, korean, value) in enumerate(_variable_fields_from_schema(schema), start=1):
                _execute(
                    cur,
                    """
                    INSERT INTO template_fields (template_id_num, field_key, korean_label, value, sort_order)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tid_num, key, korean, value, index),
                    desc=f"가변 필드 '{key}' 저장",
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        f"[template_save] id={template_id} has_schema={schema is not None}",
        flush=True,
    )


def load_templates() -> list[PromptTemplate]:
    """활성 템플릿 전부 로드 — 목록 화면 없이 매칭용으로만 쓰여서 상세까지 항상 조회.
    템플릿 개수(N)와 무관하게 쿼리 3번 고정(목록1 + 라벨 IN절1 + 필드 IN절1) —
    템플릿마다 쿼리 2번씩 도는 N+1을 피한다.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        _execute(
            cur,
            """
            SELECT template_id_num, template_code, template_name, metadata_name, doc_type, prompt, doc_match_labels,
                   created_by, created_at, updated_by, updated_at
            FROM template_registry
            WHERE is_active = 1
            """,
            desc="활성 템플릿 전체 목록 조회",
        )
        rows = cur.fetchall()
        if not rows:
            return []

        tid_nums = [int(row["template_id_num"]) for row in rows]
        placeholders = ", ".join(["?"] * len(tid_nums))

        _execute(
            cur,
            f"""
            SELECT template_id_num, field_key, korean_label, value
            FROM template_fields
            WHERE template_id_num IN ({placeholders})
            ORDER BY template_id_num ASC, sort_order ASC, field_id_num ASC
            """,
            tuple(tid_nums),
            desc=f"템플릿 {len(tid_nums)}건의 가변 필드 일괄 조회",
        )
        fields_by_id: dict[int, list[dict]] = {}
        for r in cur.fetchall():
            fields_by_id.setdefault(int(r["template_id_num"]), []).append(r)

        templates: list[PromptTemplate] = []
        for row in rows:
            tid_num = int(row["template_id_num"])
            labels = frozenset(
                part.strip()
                for part in str(row["doc_match_labels"] or "").split(",")
                if part.strip()
            )
            field_rows = fields_by_id.get(tid_num, [])

            schema: dict[str, Any] | None = None
            if row["metadata_name"] or row["doc_type"] or field_rows:
                raw_schema: dict[str, Any] = {
                    "DOC_TYPE": row["doc_type"] or "",
                    "METADATA_NAME": row["metadata_name"] or "",
                    "DESCRIPTION": "",
                    "template_created_by": row["created_by"] or "",
                    "template_created_at": _format_audit_timestamp(row["created_at"]),
                    "template_updated_by": row["updated_by"] or "",
                    "template_updated_at": _format_audit_timestamp(row["updated_at"]),
                }
                search_labels: dict[str, str] = {}
                for f in field_rows:
                    raw_schema[f["field_key"]] = f["value"] or ""
                    if f["korean_label"]:
                        search_labels[f["field_key"]] = f["korean_label"]
                if search_labels:
                    raw_schema[SEARCH_LABELS_KEY] = search_labels
                schema = normalize_result_schema(raw_schema)

            templates.append(
                PromptTemplate(
                    template_id=row["template_code"],
                    name=row["template_name"],
                    labels=labels,
                    prompt=row["prompt"] or "",
                    result_schema=schema,
                    doc_type=row["doc_type"],
                )
            )
        return templates
    finally:
        conn.close()


def soft_delete_template(template_id: str) -> None:
    """활성 템플릿을 is_active=0으로 — 진짜 삭제 아님(PDF 타입과 동일 패턴)."""
    tid = (template_id or "").strip()
    if not tid:
        raise ValueError("template_id가 비어 있습니다.")

    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        _execute(
            cur,
            "SELECT template_id_num, is_active FROM template_registry WHERE template_code = ?",
            (tid,),
            desc=f"삭제 대상 템플릿 조회 (template_code='{tid}')",
        )
        row = cur.fetchone()
        if not row:
            raise FileNotFoundError(f"템플릿 파일이 없습니다: {tid}.json")
        if not row["is_active"]:
            raise ValueError(f"이미 soft-delete 된 template_id 입니다: {tid}")

        _execute(
            cur,
            "UPDATE template_registry SET is_active = 0 WHERE template_id_num = ?",
            (int(row["template_id_num"]),),
            desc=f"템플릿 비활성화(소프트 삭제) (template_code='{tid}')",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[template_soft_delete] id={tid}", flush=True)
