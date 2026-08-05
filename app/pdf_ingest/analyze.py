"""PDF 바이트 검사·메타 추출 (적재 전 inspect / ingest 공통)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from ingest.load_pdf import load_pdf_pages

try:
    from app.pdf_ingest.doc_metadata import build_doc_metadata_fields
except ImportError:  # pragma: no cover
    def build_doc_metadata_fields(pdf_path, *, source_file=None):  # type: ignore[misc]
        from pathlib import Path as _P

        stem = _P(source_file or _P(pdf_path).name).stem
        from datetime import datetime, timezone

        return {
            "title": stem or "document",
            "created_date": datetime.now(timezone.utc).date().isoformat(),
        }

try:
    from app.pdf_ingest.doc_kind import DOC_KIND_TABLE, classify_document_kind
except ImportError:  # pragma: no cover
    DOC_KIND_TABLE = 3

    def classify_document_kind(*, page_count, text, pdf_path=None, min_table_rows=10):  # type: ignore[misc]
        return 1


try:
    from app.pdf_ingest.metadata_extract import extract_metadata_candidates
    from app.pdf_ingest.structure_fingerprint import extract_structure_fingerprint
except ImportError:  # pragma: no cover
    def extract_metadata_candidates(text, *, known_labels=()):  # type: ignore[misc]
        return []

    def extract_structure_fingerprint(text, *, known_labels=()):  # type: ignore[misc]
        return frozenset()


try:
    from app.pdf_ingest.text_truncate import truncate_repeating_table_rows
except ImportError:  # pragma: no cover
    def truncate_repeating_table_rows(pdf_path, *, max_rows_per_table=0):  # type: ignore[misc]
        return ""


def _log_doc_kind(filename: str, kind: int) -> None:
    """판별 결과만 한 줄 (logs/doc_kind.log)."""
    line = f"[doc_kind] file={filename} kind={kind}"
    print(line, flush=True)
    log_path = Path(__file__).resolve().parents[2] / "logs" / "doc_kind.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _log_text_truncate(*, filename: str, before: int, after: int) -> None:
    """kind=3 반복 행 전처리 — 테스트 확인용 한 줄."""
    line = f"[text_truncate] file={filename} before_chars={before} after_chars={after}"
    print(line, flush=True)
    log_path = Path(__file__).resolve().parents[2] / "logs" / "text_truncate.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def analyze_pdf_bytes(
    filename: str,
    content: bytes,
    *,
    template_labels_by_doc_type: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """임시 파일로 로드 후 페이지·기본/특화 메타·문서특성·구조 지문을 반환.

    Returns:
        is_fable_card, page_count, basic_metadata, fable_metadata(nullable),
        document_kind (1~4), structure_labels (라벨 이름 목록)
    """
    safe_name = Path(filename or "upload.pdf").name
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    with tempfile.TemporaryDirectory(prefix="pdf_inspect_") as tmp:
        path = Path(tmp) / safe_name
        path.write_bytes(content)
        pages = load_pdf_pages(path)
        joined = "\n".join(p.text for p in pages if p.text and p.text.strip())
        doc_fields = build_doc_metadata_fields(path, source_file=safe_name)
        # 표 판별은 PDF 구조(find_tables). 텍스트 '|' 휴리스틱 사용 안 함
        document_kind = classify_document_kind(
            page_count=len(pages),
            text=joined,
            pdf_path=path,
        )
        _log_doc_kind(safe_name, int(document_kind))
        from app.pdf_ingest.global_labels import doc_kind_to_letter

        doc_type = doc_kind_to_letter(document_kind)
        known_labels = tuple(
            (template_labels_by_doc_type or {}).get(doc_type, ())
        )
        extracted_metadata = extract_metadata_candidates(
            joined,
            known_labels=known_labels,
        )
        structure_labels = sorted(
            extract_structure_fingerprint(
                joined,
                known_labels=known_labels,
            )
        )
        print(
            f"[structure_fp] file={safe_name} kind={document_kind} "
            f"label_count={len(structure_labels)} labels={structure_labels}",
            flush=True,
        )

        basic = {
            "source_file": safe_name,
            "page_count": len(pages),
            "char_count": len(joined),
            "title": doc_fields["title"],
            "created_date": doc_fields["created_date"],
        }
        # kind=3만 find_tables 전처리. 1번에는 적용 안 함. 후처리 배열 삭제 없음
        excerpt = joined[:20000]
        if int(document_kind) == int(DOC_KIND_TABLE):
            before_len = len(excerpt)
            excerpt = truncate_repeating_table_rows(path)
            _log_text_truncate(
                filename=safe_name,
                before=before_len,
                after=len(excerpt),
            )

        return {
            # 레거시 응답 필드는 호환용으로 유지하되 A 본줄은 특화 파서를 사용하지 않는다.
            "is_fable_card": False,
            "page_count": len(pages),
            "basic_metadata": basic,
            "fable_metadata": None,
            "document_kind": document_kind,
            "structure_labels": structure_labels,
            "extracted_metadata": extracted_metadata,
            "text_excerpt": excerpt,
        }
