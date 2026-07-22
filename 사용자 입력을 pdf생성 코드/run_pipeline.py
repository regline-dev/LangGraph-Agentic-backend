"""
전체 흐름: 원문 텍스트만 넣으면 -> LLM 채점 -> PDF 생성까지 한 번에 처리.

    사용자 입력(원문) -> score_fable_with_llm() -> generate_fable_pdf() -> PDF 파일

사용법:
    python run_pipeline.py <원문.txt> <id> <출력.pdf>

예:
    python run_pipeline.py wolf_lamb.txt 1 output.pdf
"""
import sys

from fable_scorer import score_fable_with_llm
from fable_pdf_generator import generate_fable_pdf

SOURCE_NOTE_DEFAULT = "1867년 타운센드 영역본 기반 우리말 번역, 이솝우화 도감"


def run_pipeline(body_text: str, id: int, output_path: str,
                  source_note: str = SOURCE_NOTE_DEFAULT) -> str:
    # 1~2단계: LLM 채점 (내용 평가 + 제목/부제까지 원문에서 자동 생성)
    scored = score_fable_with_llm(body_text)

    # 3단계: 채점 결과 + 원문 + 메타를 하나의 데이터로 합침
    data = {
        "id": id,
        "body_text": body_text,  # PDF엔 인쇄 안 됨, 구조 통계 계산에만 쓰임
        "source_note": source_note,
        **scored,  # title, subtitle, fun, violence, moral_clarity, ending_tone, tags, characters, modern_take
    }

    # 4단계: PDF 생성 (구조 정보는 여기서 자동 계산됨 - LLM 불필요)
    return generate_fable_pdf(data, output_path)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print('사용법: python run_pipeline.py <원문.txt> <id> <출력.pdf>')
        sys.exit(1)

    _, text_path, fid, out_path = sys.argv

    with open(text_path, encoding="utf-8") as f:
        body = f.read()

    result_path = run_pipeline(body, int(fid), out_path)
    print(f"생성 완료: {result_path}")
