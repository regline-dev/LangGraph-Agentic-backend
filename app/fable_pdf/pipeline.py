"""원문 → 채점 → PDF 파일 (CLI run_pipeline 과 동일 흐름)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

from app.fable_pdf.pdf_generator import generate_fable_pdf
from app.fable_pdf.scorer import score_fable_with_llm

SOURCE_NOTE_DEFAULT = "1867년 타운센드 영역본 기반 우리말 번역, 이솝우화 도감"

# 호출 시그니처: (body_text, fable_id, output_path, source_note) -> scored meta dict
FablePipelineFn = Callable[[str, int, str, str], dict[str, Any]]


def run_fable_pipeline(
    body_text: str,
    fable_id: int,
    output_path: str,
    source_note: str = SOURCE_NOTE_DEFAULT,
    *,
    timeout_seconds: float = 100.0,
) -> dict[str, Any]:
    """
    Groq 채점 후 PDF를 output_path에 쓴다.
    반환: title/subtitle 등 채점 메타 (응답 헤더용).
    timeout_seconds 초과 시 TimeoutError.
    """

    def _work() -> dict[str, Any]:
        scored = score_fable_with_llm(body_text, timeout_seconds=timeout_seconds)
        data = {
            "id": fable_id,
            "body_text": body_text,
            "source_note": source_note or SOURCE_NOTE_DEFAULT,
            **scored,
        }
        generate_fable_pdf(data, output_path)
        return {
            "title": str(scored.get("title") or ""),
            "subtitle": str(scored.get("subtitle") or ""),
            "fun": scored.get("fun"),
            "violence": scored.get("violence"),
            "moral_clarity": scored.get("moral_clarity"),
            "ending_tone": scored.get("ending_tone"),
        }

    # HTTP 워커를 막지 않도록 스레드에서 실행 + 전체 한도
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_work)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeout as exc:
            raise TimeoutError(
                f"채점·PDF 생성이 {int(timeout_seconds)}초를 초과했습니다."
            ) from exc
