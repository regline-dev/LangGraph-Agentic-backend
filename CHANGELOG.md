# LangGraph-Agentic-backend CHANGELOG

PDF 모드용 LangGraph Agentic 백엔드 계획·구조·구현 변경 이력.
파일에 버전을 표기하지 않고 이 문서에 누적한다.

---

## 2026-07-17 (v1)

**변경 파일**: LangGraph-Agentic-backend/README.md, LangGraph-Agentic-backend/CHANGELOG.md

**변경 내용**: PDF 모드용 LangGraph Agentic 백엔드 레포를 착수하고 README 기준 구조를 정리

- PDF 사용자 검색은 LangGraph의 LLM 판단 → Tool 검색 → Observation 루프로 구현한다고 명시
- FAQ `qa_*` 벡터와 PDF 청크 벡터를 분리하고, API 진입점은 `POST /agent/chat`으로 정리
- 인제스트는 일방향/Agentic 여부를 아직 미결정으로 두고, Phase 0.5에서는 기본 일방향 인덱싱으로 검색 연료만 준비
- 원본 계획은 `Docs/20260715_FAQ_PDF모드_LangGraph분리_계획.md`, `Docs/20260715_RAG_Agent_다이어그램_부록.md`를 기준으로 함
