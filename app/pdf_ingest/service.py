"""PDF 업로드 → data/uploads → Qdrant 적재 (2차-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qdrant_client.http import models as qmodels

from app.config import Settings, get_settings
from app.pdf_ingest.analyze import analyze_pdf_bytes
from app.pdf_ingest.document_version import (
    compute_content_hash,
    mark_document_version_indexed,
    preview_document_version,
    resolve_document_version,
)
from app.pdf_ingest.template_match import (
    match_fingerprint_to_templates,
    match_filename_to_templates,
)
from app.pdf_ingest.template_service import load_templates, save_template, soft_delete_template
from app.pdf_ingest.template_store import (
    PromptTemplate,
    has_result_schema,
    resolve_template_prompt,
)
from app.qdrant_factory import get_shared_qdrant_client
from ingest.embedder_factory import create_embedder
from ingest.index_documents import DEFAULT_UPLOADS_DIR, ingest_pdf


@dataclass(frozen=True)
class PdfIngestResult:
    """HTTP 응답용 적재 결과."""

    source_file: str
    indexed: int
    collection: str
    page_count: int = 0
    metadata: dict[str, Any] | None = None  # 이솝 특화 (없으면 null)
    basic_metadata: dict[str, Any] = field(default_factory=dict)
    is_fable_card: bool = False
    # 문서 버전 관리(계획: Docs/20260814_벡터화_문서버전관리_계획.md)
    document_version_action: str = "new_document"  # skip | new_document | new_version
    document_id: int | None = None
    version: int = 1
    content_hash: str = ""


@dataclass(frozen=True)
class PdfInspectResult:
    """적재 없이 카드 여부·메타·지문·템플릿 매칭."""

    is_fable_card: bool
    page_count: int
    basic_metadata: dict[str, Any]
    fable_metadata: dict[str, Any] | None = None
    document_kind: int = 1  # 1 일반텍스트 · 2 스캔 · 3 표 · 4 복합
    structure_labels: list[str] = field(default_factory=list)
    extracted_metadata: list[dict[str, str]] = field(default_factory=list)
    template_match_status: str = "no_match"  # match | ambiguous | no_match
    template_id: str | None = None
    template_prompt: str | None = None
    prompt_locked: bool = False
    template_candidates: list[dict[str, Any]] = field(default_factory=list)
    text_excerpt: str = ""
    # 맞음일 때 결과 양식 템플릿 (없으면 None)
    result_schema: dict[str, Any] | None = None
    # 맞음+결과양식일 때 서버가 문서값으로 채운 결과 (UI 자동 표시)
    filled_result: dict[str, Any] | None = None
    # 1차 판단(예고) — 계획: Docs/20260814_벡터화_문서버전관리_계획.md
    document_version_preview_action: str = "new_document"  # skip | new_document | new_version
    document_id: int | None = None
    content_hash: str = ""


class PdfIngestService:
    """업로드 바이트를 uploads에 저장한 뒤 컬렉션에 적재한다."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        uploads_dir: Path | None = None,
        client=None,
        embedder=None,
        collection_name: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._uploads_dir = (uploads_dir or DEFAULT_UPLOADS_DIR).resolve()
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name or self._settings.qdrant_collection

    def _ensure_embedder(self):
        """PDF 분석(pymupdf) 전에 임베더를 연다.

        Windows에서 inspect 이후 ingest 때 bge-m3를 열면 0xC0000005로 프로세스가 죽는다.
        주입된 FakeEmbedder는 그대로 둔다.
        """
        if self._embedder is None:
            backend = (self._settings.embedding_backend or "bge-m3").strip()
            try:
                self._embedder = create_embedder(self._settings)
            except Exception as exc:  # noqa: BLE001
                print(
                    "[embedder_warmup] phase=service "
                    f"backend={backend} result=failure\n"
                    f"  reason={exc}",
                    flush=True,
                )
                raise
            print(
                f"[embedder_warmup] phase=service backend={backend} result=success",
                flush=True,
            )
        return self._embedder

    def _has_vectors_for_document(self, document_id: int) -> bool:
        client = self._client or get_shared_qdrant_client(self._settings)
        return _document_has_vectors(client, self._collection_name, document_id)

    def inspect(self, filename: str, content: bytes) -> PdfInspectResult:
        """적재 없이 카드 여부·메타만."""
        if not content:
            raise ValueError("빈 PDF 파일입니다.")
        if not content.lstrip().startswith(b"%PDF"):
            raise ValueError("PDF 형식이 아닙니다.")
        self._ensure_embedder()
        templates = load_templates()
        info = analyze_pdf_bytes(
            filename,
            content,
            template_labels_by_doc_type=_group_template_labels_by_doc_type(
                templates
            ),
        )
        labels = list(info.get("structure_labels") or [])
        document_kind = int(info.get("document_kind") or 1)
        extracted_metadata = list(info.get("extracted_metadata") or [])
        # ②: 파일명 키워드 매칭 먼저 시도 — 안 되면 ③ 구조 라벨 비교로 넘어감
        # (① METADATA_NAME 텍스트 직접비교는 프론트에서 함, Docs/20260812 계획)
        match = match_filename_to_templates(
            filename,
            templates,
            document_kind=document_kind,
        )
        if match.status != "match":
            match = match_fingerprint_to_templates(
                frozenset(labels),
                templates,
                document_kind=document_kind,
            )
        matched = match.template
        candidates = [
            {
                "template_id": item.template_id,
                "name": item.name,
                "prompt": item.prompt,
                "has_result_schema": has_result_schema(item),
            }
            for item in (match.candidates or [])
        ]
        result_schema = None
        filled_result = None
        template_prompt = None
        if matched is not None:
            if has_result_schema(matched):
                result_schema = dict(matched.result_schema or {})
                from app.pdf_ingest.fill_template_meta import fill_result_schema_from_document

                filled_result = fill_result_schema_from_document(
                    result_schema,
                    basic_metadata=dict(info["basic_metadata"]),
                    text_excerpt=str(info.get("text_excerpt") or ""),
                    document_kind=document_kind,
                    extracted_metadata=extracted_metadata,
                )
            template_prompt = resolve_template_prompt(matched)

        content_hash = compute_content_hash(content)
        preview = preview_document_version(
            collection=self._collection_name,
            source_file=_safe_pdf_filename(filename),
            content_hash=content_hash,
            has_vectors=self._has_vectors_for_document,
        )
        print(
            f"[inspect] file={filename} kind={info.get('document_kind')} "
            f"status={match.status} template_id="
            f"{matched.template_id if matched else None} "
            f"filled={'yes' if filled_result else 'no'} "
            f"doc_labels={labels}",
            flush=True,
        )
        return PdfInspectResult(
            is_fable_card=bool(info["is_fable_card"]),
            page_count=int(info["page_count"]),
            basic_metadata=dict(info["basic_metadata"]),
            fable_metadata=info.get("fable_metadata"),
            document_kind=document_kind,
            structure_labels=labels,
            extracted_metadata=extracted_metadata,
            template_match_status=match.status,
            template_id=matched.template_id if matched else None,
            template_prompt=template_prompt,
            prompt_locked=bool(match.prompt_locked),
            template_candidates=candidates,
            text_excerpt=str(info.get("text_excerpt") or ""),
            result_schema=result_schema,
            filled_result=filled_result,
            document_version_preview_action=preview.action,
            document_id=preview.document_id,
            content_hash=content_hash,
        )

    def save_prompt_template(
        self,
        *,
        template_id: str,
        name: str,
        labels: list[str],
        prompt: str = "",
        result_schema: dict | None = None,
    ) -> PromptTemplate:
        """판별용 labels + 결과 양식(또는 탐색 지시문) 저장."""
        from app.pdf_ingest.global_labels import normalize_result_schema

        schema = None
        if isinstance(result_schema, dict) and result_schema:
            # 전역 키 전부·GLOBAL 순서·가변·search_labels 맨 끝
            schema = normalize_result_schema(result_schema)
        template = PromptTemplate(
            template_id=template_id.strip(),
            name=(name or template_id).strip(),
            labels=frozenset(str(label).strip() for label in labels if str(label).strip()),
            prompt=(prompt or "").strip(),
            result_schema=schema,
            doc_type=(
                str(schema.get("DOC_TYPE") or "").strip().upper()
                if isinstance(schema, dict)
                else None
            ),
        )
        save_template(template)
        return template

    def list_prompt_templates(self) -> list[dict[str, Any]]:
        """저장된 결과 양식 템플릿 목록 (METADATA_NAME 포함)."""
        from app.pdf_ingest.global_labels import extract_metadata_name_from_schema

        rows: list[dict[str, Any]] = []
        for item in load_templates():
            schema = dict(item.result_schema) if isinstance(item.result_schema, dict) else None
            rows.append(
                {
                    "template_id": item.template_id,
                    "name": item.name,
                    "metadata_name": extract_metadata_name_from_schema(schema),
                    "labels": sorted(item.labels),
                    "has_result_schema": has_result_schema(item),
                    "result_schema": schema,
                }
            )
        return rows

    def delete_prompt_template(
        self,
        *,
        template_id: str,
        delete_vectors: bool = False,
    ) -> dict[str, Any]:
        """템플릿 soft-delete. delete_vectors=True 이면 payload.template_id 로 Qdrant 삭제."""
        tid = (template_id or "").strip()
        if not tid:
            raise ValueError("template_id가 비어 있습니다.")

        soft_delete_template(tid)
        deleted_vectors = 0
        if delete_vectors:
            client = self._client or get_shared_qdrant_client(self._settings)
            deleted_vectors = _delete_by_template_id(
                client, self._collection_name, tid
            )
        return {
            "template_id": tid,
            "soft_deleted": True,
            "delete_vectors": bool(delete_vectors),
            "deleted_vector_points": deleted_vectors,
        }

    def __call__(
        self,
        filename: str,
        content: bytes,
        prompt: str | None = None,
    ) -> PdfIngestResult:
        safe_name = _safe_pdf_filename(filename)
        if not content:
            raise ValueError("빈 PDF 파일입니다.")
        if not content.lstrip().startswith(b"%PDF"):
            raise ValueError("PDF 형식이 아닙니다.")

        self._ensure_embedder()
        templates = load_templates()
        analyzed = analyze_pdf_bytes(
            safe_name,
            content,
            template_labels_by_doc_type=_group_template_labels_by_doc_type(
                templates
            ),
        )

        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        destination = self._uploads_dir / safe_name
        destination.write_bytes(content)

        client = self._client or get_shared_qdrant_client(self._settings)
        embedder = self._embedder or create_embedder(self._settings)
        collection = self._collection_name

        # 2차 판단(벡터화 시작 시점 확정) — 계획: Docs/20260814_벡터화_문서버전관리_계획.md
        content_hash = compute_content_hash(content)
        decision = resolve_document_version(
            collection=collection,
            source_file=safe_name,
            content_hash=content_hash,
            page_count=int(analyzed["page_count"]),
            has_vectors=self._has_vectors_for_document,
        )

        from app.pdf_ingest.admin_meta import parse_admin_meta_json

        prompt_text = (prompt or "").strip() or None
        admin_meta = parse_admin_meta_json(prompt_text) if prompt_text else None
        # 벡터 삭제 필터용 — METADATA_NAME 으로 활성 템플릿을 찾아 template_id 스탬프
        if isinstance(admin_meta, dict) and not admin_meta.get("template_id"):
            from app.pdf_ingest.global_labels import extract_metadata_name_from_schema

            meta_name = extract_metadata_name_from_schema(admin_meta)
            if meta_name:
                for item in templates:
                    if extract_metadata_name_from_schema(item.result_schema) == meta_name:
                        admin_meta = {**admin_meta, "template_id": item.template_id}
                        break

        # 운영자 프롬프트·결과 JSON은 응답 메타에 보존
        basic_metadata = dict(analyzed["basic_metadata"])
        fable_metadata = analyzed.get("fable_metadata")
        if prompt_text:
            basic_metadata = {**basic_metadata, "prompt": prompt_text}
            if isinstance(fable_metadata, dict):
                fable_metadata = {**fable_metadata, "prompt": prompt_text}
        if admin_meta and isinstance(admin_meta.get("search_labels"), dict):
            basic_metadata = {
                **basic_metadata,
                "search_labels": dict(admin_meta["search_labels"]),
            }

        if decision.action == "skip":
            # 같은 문서ID·같은 콘텐츠 해시 — 임베딩·업서트 생략
            return PdfIngestResult(
                source_file=safe_name,
                indexed=0,
                collection=collection,
                page_count=int(analyzed["page_count"]),
                metadata=fable_metadata,
                basic_metadata=basic_metadata,
                is_fable_card=bool(analyzed["is_fable_card"]),
                document_version_action="skip",
                document_id=decision.document_id,
                version=decision.version,
                content_hash=content_hash,
            )

        if decision.action == "new_document":
            # document_id 체계 이전에 쌓인 포인트까지 정리(안전장치)
            _delete_by_source_file(client, collection, safe_name)
        else:
            # 예전 버전은 지우지 않고 is_current만 내림(이력 보존)
            _mark_previous_version_stale(client, collection, decision.document_id)

        indexed = ingest_pdf(
            destination,
            client=client,
            collection_name=collection,
            embedder=embedder,
            uploads_dir=self._uploads_dir,
            admin_meta=admin_meta,
            version_meta={
                "document_id": decision.document_id,
                "content_hash": content_hash,
                "version": decision.version,
                "is_current": True,
            },
        )
        mark_document_version_indexed(
            decision.document_id, decision.version, indexed=indexed
        )

        return PdfIngestResult(
            source_file=safe_name,
            indexed=indexed,
            collection=collection,
            page_count=int(analyzed["page_count"]),
            metadata=fable_metadata,
            basic_metadata=basic_metadata,
            is_fable_card=bool(analyzed["is_fable_card"]),
            document_version_action=decision.action,
            document_id=decision.document_id,
            version=decision.version,
            content_hash=content_hash,
        )


def _group_template_labels_by_doc_type(
    templates: list[PromptTemplate],
) -> dict[str, frozenset[str]]:
    """템플릿 설정의 DOC_TYPE별 원문 라벨 사전을 만든다."""
    grouped: dict[str, set[str]] = {}
    for template in templates:
        doc_type = str(template.doc_type or "").strip().upper()
        if not doc_type:
            continue
        grouped.setdefault(doc_type, set()).update(template.labels)
        schema = template.result_schema
        search_labels = (
            schema.get("search_labels")
            if isinstance(schema, dict)
            else None
        )
        if isinstance(search_labels, dict):
            grouped[doc_type].update(
                str(label).strip()
                for label in search_labels.values()
                if str(label).strip()
            )
    return {
        doc_type: frozenset(labels)
        for doc_type, labels in grouped.items()
    }


def _safe_pdf_filename(filename: str) -> str:
    """경로 조작 방지 · PDF만 허용."""
    name = Path(filename or "").name.strip()
    if not name:
        raise ValueError("파일명이 비어 있습니다.")
    if Path(name).suffix.lower() != ".pdf":
        raise ValueError("PDF 파일만 업로드할 수 있습니다.")
    return name


def _document_has_vectors(client, collection: str, document_id: int) -> bool:
    """해당 document_id 포인트가 컬렉션에 하나라도 있으면 True."""
    try:
        existing = {item.name for item in client.get_collections().collections}
        if collection not in existing:
            return False
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return bool(points)
    except Exception:  # noqa: BLE001
        return False


def _delete_by_source_file(client, collection: str, source_file: str) -> None:
    """동일 source_file 포인트 삭제 (재업로드 대비)."""
    existing = {item.name for item in client.get_collections().collections}
    if collection not in existing:
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


def _mark_previous_version_stale(client, collection: str, document_id: int) -> None:
    """새 버전 추가 시 예전 버전 포인트를 지우지 않고 is_current만 false로 내린다."""
    existing = {item.name for item in client.get_collections().collections}
    if collection not in existing:
        return
    client.set_payload(
        collection_name=collection,
        payload={"is_current": False},
        points=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id),
                )
            ]
        ),
    )


def _delete_by_template_id(client, collection: str, template_id: str) -> int:
    """payload.template_id 일치 포인트 삭제. 삭제 요청 건수(알 수 없으면 0)."""
    tid = (template_id or "").strip()
    if not tid:
        return 0
    existing = {item.name for item in client.get_collections().collections}
    if collection not in existing:
        return 0
    # 삭제 전 개수(대략) — scroll 없이 필터 delete 만 수행
    client.delete(
        collection_name=collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="template_id",
                        match=qmodels.MatchValue(value=tid),
                    )
                ]
            )
        ),
    )
    print(
        f"[template_vector_delete] collection={collection} template_id={tid}",
        flush=True,
    )
    return 0


_default_service: PdfIngestService | None = None


def get_pdf_ingest_service() -> PdfIngestService:
    """FastAPI Depends용 싱글톤."""
    global _default_service
    if _default_service is None:
        _default_service = PdfIngestService()
    return _default_service
