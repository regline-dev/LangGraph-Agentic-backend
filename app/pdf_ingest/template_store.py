"""양식 저장소 — 판별용(labels) + 결과 양식(result_schema) + 탐색 지시문(prompt).

용어:
  - 판별용 템플릿: labels 로 같은 PDF 패턴인지 판별
  - 결과 양식 템플릿: result_schema (확정 메타 JSON 구조)
  - 탐색 지시문: prompt — 결과 양식 없을 때만 사용 (레거시 포함)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TEMPLATE_STORE_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "prompt_templates"
)


@dataclass(frozen=True)
class PromptTemplate:
    """저장된 양식 1건 (판별용 labels + 선택적 결과 양식/탐색 지시문)."""

    template_id: str
    name: str
    labels: frozenset[str]
    prompt: str = ""
    result_schema: dict[str, Any] | None = None
    doc_type: str | None = None


def has_result_schema(template: PromptTemplate) -> bool:
    """결과 양식 템플릿이 있는지."""
    schema = template.result_schema
    return isinstance(schema, dict) and len(schema) > 0


def has_fill_lock(template: PromptTemplate) -> bool:
    """맞음일 때 지시문을 잠글지 — 결과 양식 또는 (레거시) 탐색 지시문이 있을 때."""
    if has_result_schema(template):
        return True
    return bool((template.prompt or "").strip())


def build_result_schema_fill_prompt(result_schema: dict[str, Any]) -> str:
    """결과 양식 템플릿 → 다음 PDF용 채우기 지시문."""
    schema_json = json.dumps(result_schema, ensure_ascii=False, indent=2)
    return (
        "당신은 문서에서 메타데이터를 추출합니다.\n"
        "아래 「결과 양식」의 키와 계층 구조를 그대로 유지하고, "
        "새 문서 내용으로 값만 채운 JSON 객체만 출력하세요.\n"
        "양식에 없는 키를 추가하지 마세요. 설명·코드펜스·원문 재출력 금지.\n\n"
        f"결과 양식:\n{schema_json}"
    )


def resolve_template_prompt(template: PromptTemplate) -> str | None:
    """맞음일 때 UI/LLM에 넣을 지시문. 결과 양식 우선."""
    if has_result_schema(template):
        assert template.result_schema is not None
        return build_result_schema_fill_prompt(template.result_schema)
    text = (template.prompt or "").strip()
    return text or None


def save_template(
    template: PromptTemplate,
    *,
    store_dir: Path | None = None,
) -> Path:
    """양식을 JSON 파일로 저장. 판별 labels 필수. 결과 양식 또는 탐색 지시문 중 하나 필수."""
    if not template.labels:
        raise ValueError("판별용 labels가 비어 있습니다.")
    template_id = (template.template_id or "").strip()
    if not template_id:
        raise ValueError("template_id가 비어 있습니다.")

    prompt_text = (template.prompt or "").strip()
    schema = template.result_schema if isinstance(template.result_schema, dict) else None
    if schema is not None and len(schema) == 0:
        schema = None
    if schema is None and not prompt_text:
        raise ValueError("결과 양식(result_schema) 또는 탐색 지시문(prompt)이 필요합니다.")

    target_dir = (store_dir or DEFAULT_TEMPLATE_STORE_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{template_id}.json"
    already = path.is_file()
    payload: dict[str, Any] = {
        "template_id": template_id,
        "name": (template.name or template_id).strip(),
        "labels": sorted(template.labels),
        "prompt": prompt_text,
    }
    if template.doc_type:
        payload["doc_type"] = template.doc_type
    if schema is not None:
        payload["result_schema"] = schema
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[template_save] id={template_id} path={path.name} "
        f"labels={sorted(template.labels)} "
        f"has_schema={schema is not None} overwrite={already}",
        flush=True,
    )
    return path


def load_templates(*, store_dir: Path | None = None) -> list[PromptTemplate]:
    """디렉터리의 *.json 양식을 모두 로드. *_delete.json 은 제외. 없으면 빈 목록."""
    target_dir = (store_dir or DEFAULT_TEMPLATE_STORE_DIR).resolve()
    if not target_dir.is_dir():
        return []

    templates: list[PromptTemplate] = []
    for path in sorted(target_dir.glob("*.json")):
        if is_soft_deleted_template_path(path):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        template = _from_dict(data)
        if template is not None:
            templates.append(template)
    return templates


SOFT_DELETE_SUFFIX = "_delete"


def is_soft_deleted_template_path(path: Path) -> bool:
    """파일명이 {template_id}_delete.json 이면 soft-delete 보관본."""
    return path.stem.endswith(SOFT_DELETE_SUFFIX)


def soft_delete_template(
    template_id: str,
    *,
    store_dir: Path | None = None,
) -> Path:
    """활성 템플릿 파일을 {template_id}_delete.json 으로 rename (진짜 삭제 아님)."""
    tid = (template_id or "").strip()
    if not tid:
        raise ValueError("template_id가 비어 있습니다.")
    if tid.endswith(SOFT_DELETE_SUFFIX):
        raise ValueError("이미 soft-delete 된 template_id 입니다.")

    target_dir = (store_dir or DEFAULT_TEMPLATE_STORE_DIR).resolve()
    src = target_dir / f"{tid}.json"
    if not src.is_file():
        raise FileNotFoundError(f"템플릿 파일이 없습니다: {tid}.json")

    dest = target_dir / f"{tid}{SOFT_DELETE_SUFFIX}.json"
    if dest.is_file():
        dest.unlink()
    src.rename(dest)
    print(
        f"[template_soft_delete] id={tid} from={src.name} to={dest.name}",
        flush=True,
    )
    return dest


def _from_dict(data: Any) -> PromptTemplate | None:
    if not isinstance(data, dict):
        return None
    template_id = str(data.get("template_id") or "").strip()
    prompt = str(data.get("prompt") or "").strip()
    raw_labels = data.get("labels") or []
    if not template_id or not isinstance(raw_labels, list):
        return None
    labels = frozenset(str(label).strip() for label in raw_labels if str(label).strip())
    if not labels:
        return None
    name = str(data.get("name") or template_id).strip()
    raw_schema = data.get("result_schema")
    result_schema: dict[str, Any] | None = None
    if isinstance(raw_schema, dict) and raw_schema:
        result_schema = raw_schema
    raw_doc_type = data.get("doc_type")
    if raw_doc_type in (None, "") and result_schema is not None:
        raw_doc_type = result_schema.get("DOC_TYPE")
    doc_type = str(raw_doc_type or "").strip().upper() or None
    return PromptTemplate(
        template_id=template_id,
        name=name,
        labels=labels,
        prompt=prompt,
        result_schema=result_schema,
        doc_type=doc_type,
    )
