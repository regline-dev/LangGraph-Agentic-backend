"""Hetzner(터널)에 template_registry / template_labels / template_fields 생성. 시드 없음(수동 재등록)."""

from __future__ import annotations

import os
from pathlib import Path

import mariadb
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
SQL_PATH = BASE / "sql" / "create_template_tables.sql"
load_dotenv(BASE / ".env")


def split_sql_statements(sql_text: str) -> list[str]:
    """주석·빈 줄 제거 후 세미콜론 단위로 나눈다."""
    lines: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    return [part.strip() for part in cleaned.split(";") if part.strip()]


def main() -> None:
    print(
        f"[migrate_template_tables] host={os.getenv('DB_HOST')} "
        f"db={os.getenv('DB_NAME')} sql={SQL_PATH.name}",
        flush=True,
    )
    if not SQL_PATH.is_file():
        raise FileNotFoundError(SQL_PATH)

    conn = mariadb.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "chatbot"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "chatbot"),
    )
    cur = conn.cursor()
    statements = split_sql_statements(SQL_PATH.read_text(encoding="utf-8"))
    for index, statement in enumerate(statements, start=1):
        preview = " ".join(statement.split())[:80]
        cur.execute(statement)
        print(f"[migrate_template_tables] ok step={index} sql={preview}", flush=True)
    conn.commit()

    cur.execute("SHOW TABLES LIKE 'template_%'")
    tables = [row[0] for row in cur.fetchall()]
    print(f"[migrate_template_tables] result=success tables={tables}", flush=True)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
