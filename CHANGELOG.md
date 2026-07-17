# LangGraph-Agentic-backend CHANGELOG

PDF 모드용 LangGraph Agentic 백엔드 계획·구조·구현 변경 이력.
파일에 버전을 표기하지 않고 이 문서에 누적한다.

---

## 2026-07-17 (v3) — Phase 0.5 완료

**변경 파일**: ingest/load_pdf.py, ingest/chunk.py, ingest/index_documents.py, app/tools/search_documents.py, tests/test_ingest.py, tests/fixtures/sample.pdf, Docs/20260717_LangGraph-Agentic-backend_Phase0.5_계획.md

**변경 내용**: Phase 0.5 — PDF 일방향 인제스트로 검색 연료 파이프라인 검증 완료

- 샘플 PDF를 로드·청킹한 뒤 FakeEmbedding과 Qdrant(`pdf_chunks`)에 적재
- `search_documents`로 연차 관련 쿼리 1건이 검색되는지 TDD로 확인 (`pytest` 4건 통과)
- 실 LLM 임베딩·LangGraph 루프는 아직 없음 (Phase 1에서 연결)

---

## 2026-07-17 (v2) — Phase 0 완료

**변경 파일**: app/main.py, app/config.py, tests/test_health.py, pyproject.toml, .env.example, Docs/20260717_LangGraph-Agentic-backend_Phase0_계획.md

**변경 내용**: Phase 0 — FastAPI 뼈대와 `GET /health` 검증 완료

- `app/main.py`에 FastAPI 앱과 `/health`(`{"status":"ok"}`) 추가
- `tests/test_health.py` TDD로 작성 후 `pytest` 1건 통과
- `pyproject.toml`·`.env.example`로 로컬 설치·실행 규약 정리 (기본 포트 8005)

---

## 2026-07-17 (v1)

**변경 파일**: LangGraph-Agentic-backend/README.md, LangGraph-Agentic-backend/CHANGELOG.md

**변경 내용**: PDF 모드용 LangGraph Agentic 백엔드 레포를 착수하고 README 기준 구조를 정리

- PDF 사용자 검색은 LangGraph의 LLM 판단 → Tool 검색 → Observation 루프로 구현한다고 명시
- FAQ `qa_*` 벡터와 PDF 청크 벡터를 분리하고, API 진입점은 `POST /agent/chat`으로 정리
- 인제스트는 일방향/Agentic 여부를 아직 미결정으로 두고, Phase 0.5에서는 기본 일방향 인덱싱으로 검색 연료만 준비
- 원본 계획은 `Docs/20260715_FAQ_PDF모드_LangGraph분리_계획.md`, `Docs/20260715_RAG_Agent_다이어그램_부록.md`를 기준으로 함
