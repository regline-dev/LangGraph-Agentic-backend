"""template_registry에 doc_match_labels 컬럼 추가, template_labels 테이블 제거.

기존 template_labels 데이터는 마이그레이션하지 않음(무시) — 결정사항.
AESOP 템플릿(template_code='A_counsel_1786445032835')만 오염된 값 대신
직접 시드값으로 doc_match_labels를 채운다.
Docs/20260812_템플릿등록_자동매칭_재설계_계획.md 참고.
"""

from __future__ import annotations

import os
from pathlib import Path

import mariadb
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

AESOP_TEMPLATE_CODE = "A_counsel_1786445032835"
AESOP_DOC_MATCH_LABELS = "결말톤,내용 평가,키워드,영상화 적합도,한마디 결론"


def main() -> None:
    print(
        f"[migrate_doc_match_labels] host={os.getenv('DB_HOST')} db={os.getenv('DB_NAME')}",
        flush=True,
    )
    conn = mariadb.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "chatbot"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "chatbot"),
    )
    cur = conn.cursor()

    cur.execute("SHOW COLUMNS FROM template_registry LIKE 'doc_match_labels'")
    if cur.fetchone():
        print("[migrate_doc_match_labels] doc_match_labels 컬럼 이미 있음 — 추가 생략", flush=True)
    else:
        cur.execute(
            """
            ALTER TABLE template_registry
            ADD COLUMN doc_match_labels VARCHAR(1024) NULL
                COMMENT '문서 라벨 매칭 — 등록 당시 문서 구조 라벨(콤마 구분, 공백 유지)'
                AFTER prompt
            """
        )
        print("[migrate_doc_match_labels] doc_match_labels 컬럼 추가 완료", flush=True)

    cur.execute(
        "UPDATE template_registry SET doc_match_labels = ? WHERE template_code = ?",
        (AESOP_DOC_MATCH_LABELS, AESOP_TEMPLATE_CODE),
    )
    print(
        f"[migrate_doc_match_labels] AESOP 시드 완료 rowcount={cur.rowcount} value={AESOP_DOC_MATCH_LABELS!r}",
        flush=True,
    )

    cur.execute("SHOW TABLES LIKE 'template_labels'")
    if cur.fetchone():
        cur.execute("DROP TABLE template_labels")
        print("[migrate_doc_match_labels] template_labels 테이블 제거 완료", flush=True)
    else:
        print("[migrate_doc_match_labels] template_labels 테이블 이미 없음", flush=True)

    conn.commit()

    cur.execute("SELECT template_code, doc_match_labels FROM template_registry WHERE is_active = 1")
    rows = cur.fetchall()
    print(f"[migrate_doc_match_labels] result=success rows={rows}", flush=True)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
