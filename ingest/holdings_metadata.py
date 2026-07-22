"""holdings schema — ETF 보유 PDF metadata 검증·청크 스탬프."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ingest.chunk import DocumentChunk

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_LOADERS = frozenset({"pdfplumber", "pymupdf", "docling"})
SCHEMA_NAME = "holdings"
ALLOWED_DOC_TYPES = frozenset({"holdings", "prospectus", "report", "unknown"})
REQUIRED_CHUNK_METADATA_KEYS = ("source_file", "as_of_date", "as_of_year")
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent / "arkk_manifest.yaml"


class MetadataRuleError(ValueError):
    """ingest metadata 계약 위반."""


def normalize_as_of_date(value: str) -> str:
    """날짜 문자열을 ISO YYYY-MM-DD로 통일."""
    if not isinstance(value, str):
        raise MetadataRuleError("as_of_date는 문자열이어야 합니다.")
    stripped = value.strip()
    if not ISO_DATE_PATTERN.match(stripped):
        raise MetadataRuleError(
            f"as_of_date는 YYYY-MM-DD 형식이어야 합니다. 입력: {value!r}"
        )
    datetime.strptime(stripped, "%Y-%m-%d")
    return stripped


def as_of_year_from_date(iso_date: str) -> int:
    """ISO 날짜에서 연도 정수 추출."""
    return date.fromisoformat(normalize_as_of_date(iso_date)).year


def validate_manifest_entry(
    entry: dict[str, Any],
    *,
    schema_def: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """holdings manifest 1행 검증·기본값 채움."""
    if not isinstance(entry, dict):
        raise MetadataRuleError("manifest 항목은 dict여야 합니다.")

    if schema_def:
        for field_name in schema_def.get("required") or []:
            if field_name not in entry or not str(entry[field_name]).strip():
                raise MetadataRuleError(f"schema=holdings 필수 필드 누락: {field_name}")

    normalized: dict[str, Any] = dict(entry)
    normalized["schema"] = SCHEMA_NAME
    normalized["path"] = str(entry["path"]).strip()
    normalized["as_of_date"] = normalize_as_of_date(str(entry["as_of_date"]))

    loader = str(entry.get("loader", "pdfplumber")).strip()
    if loader not in ALLOWED_LOADERS:
        raise MetadataRuleError(
            f"loader는 {sorted(ALLOWED_LOADERS)} 중 하나여야 합니다. 입력: {loader!r}"
        )
    normalized["loader"] = loader

    doc_type = str(entry.get("doc_type", SCHEMA_NAME)).strip()
    if doc_type not in ALLOWED_DOC_TYPES:
        raise MetadataRuleError(
            f"doc_type은 {sorted(ALLOWED_DOC_TYPES)} 중 하나여야 합니다. 입력: {doc_type!r}"
        )
    normalized["doc_type"] = doc_type

    fund_value = entry.get("fund")
    if fund_value is not None and str(fund_value).strip():
        normalized["fund"] = str(fund_value).strip()
    else:
        normalized.pop("fund", None)

    normalized["chunk_size"] = int(entry.get("chunk_size", 300))
    normalized["chunk_overlap"] = int(entry.get("chunk_overlap", 100))

    extra_value = entry.get("extra")
    if isinstance(extra_value, dict) and extra_value:
        normalized["extra"] = dict(extra_value)
    else:
        normalized.pop("extra", None)

    return normalized


def build_chunk_metadata(
    *,
    source_file: str,
    as_of_date: str,
    fund: str | None = None,
    doc_type: str = SCHEMA_NAME,
    page: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """holdings 청크 metadata dict 생성."""
    iso_date = normalize_as_of_date(as_of_date)
    metadata: dict[str, Any] = {
        "source_file": source_file.strip(),
        "as_of_date": iso_date,
        "as_of_year": as_of_year_from_date(iso_date),
        "doc_type": doc_type,
        "schema": SCHEMA_NAME,
    }
    if fund and fund.strip():
        metadata["fund"] = fund.strip()
    if page is not None:
        metadata["page"] = page
    if extra:
        metadata.update(extra)
    return validate_chunk_metadata(metadata)


def validate_chunk_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """청크 metadata 검증."""
    if not isinstance(metadata, dict):
        raise MetadataRuleError("chunk metadata는 dict여야 합니다.")

    for key in REQUIRED_CHUNK_METADATA_KEYS:
        if key not in metadata:
            raise MetadataRuleError(f"chunk 필수 metadata 누락: {key}")

    normalized = dict(metadata)
    normalized["source_file"] = str(metadata["source_file"]).strip()
    if not normalized["source_file"]:
        raise MetadataRuleError("source_file는 비어 있을 수 없습니다.")

    normalized["as_of_date"] = normalize_as_of_date(str(metadata["as_of_date"]))

    year_value = metadata["as_of_year"]
    if not isinstance(year_value, int):
        raise MetadataRuleError("as_of_year는 정수여야 합니다.")
    expected_year = as_of_year_from_date(normalized["as_of_date"])
    if year_value != expected_year:
        raise MetadataRuleError(
            f"as_of_year({year_value})와 as_of_date({normalized['as_of_date']})가 일치하지 않습니다."
        )
    normalized["as_of_year"] = year_value

    doc_type = str(metadata.get("doc_type", SCHEMA_NAME))
    if doc_type not in ALLOWED_DOC_TYPES:
        raise MetadataRuleError(f"doc_type 규칙 위반: {doc_type!r}")
    normalized["doc_type"] = doc_type

    return normalized


def apply_metadata_to_chunks(
    chunks: list[DocumentChunk],
    manifest_entry: dict[str, Any],
    *,
    source_file: str,
    schema_def: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """청크 리스트에 holdings metadata 스탬프."""
    entry = validate_manifest_entry(manifest_entry, schema_def=schema_def)
    extra_fields = entry.get("extra") or {}

    stamped: list[DocumentChunk] = []
    for chunk in chunks:
        page_number = chunk.metadata.get("page")
        new_meta = dict(chunk.metadata)
        new_meta.update(
            build_chunk_metadata(
                source_file=source_file,
                as_of_date=entry["as_of_date"],
                fund=entry.get("fund"),
                doc_type=entry.get("doc_type", SCHEMA_NAME),
                page=page_number if page_number is not None else None,
                extra=extra_fields if extra_fields else None,
            )
        )
        # chunk_id는 청킹 단계 값 유지
        if "chunk_id" in chunk.metadata:
            new_meta["chunk_id"] = chunk.metadata["chunk_id"]
        stamped.append(DocumentChunk(page_content=chunk.page_content, metadata=new_meta))

    if not stamped:
        raise MetadataRuleError(f"청크 0건 — ingest skip: {source_file}")

    return stamped


def load_arkk_manifest(manifest_path: Path | str | None = None) -> dict[str, Any]:
    """arkk_manifest.yaml에서 holdings documents 첫 항목을 읽는다."""
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
    if not path.is_file():
        raise FileNotFoundError(f"manifest 없음: {path}")

    try:
        import yaml
    except ImportError as exc:
        raise ImportError("manifest YAML 로드에 PyYAML 필요: pip install pyyaml") from exc

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise MetadataRuleError("manifest 루트는 dict여야 합니다.")

    schemas = parsed.get("schemas") or {}
    documents = parsed.get("documents") or []
    if not isinstance(documents, list) or not documents:
        raise MetadataRuleError("manifest documents가 비어 있습니다.")

    raw_entry = documents[0]
    if not isinstance(raw_entry, dict):
        raise MetadataRuleError("documents 항목은 dict여야 합니다.")

    schema_def = schemas.get("holdings") if isinstance(schemas, dict) else None
    return validate_manifest_entry(raw_entry, schema_def=schema_def)
