# LangGraph-Agentic-backend CHANGELOG

PDF 모드용 LangGraph Agentic 백엔드 계획·구조·구현 변경 이력.
파일에 버전을 표기하지 않고 이 문서에 누적한다.

---

## 2026-07-17 (v16) — QDRANT_PATH 로컬 모드 완료

**변경 파일**: app/qdrant_factory.py, app/config.py, app/graph/runtime.py, tests/test_qdrant_client.py, .env.example, README.md, Docs/20260717_LangGraph-Agentic-backend_Qdrant로컬PATH_계획.md

**변경 내용**: Qdrant를 Chroma·LangGraph와 같이 **로컬 폴더(`QDRANT_PATH`)로 붙이는 모드** 추가

- `QDRANT_PATH` 있으면 Docker 없이 path, 비면 기존 `HOST:PORT` 유지
- `/agent/chat` 검색 경로(`runtime`)가 공통 `create_qdrant_client` 사용
- `.env` 기본 예: `D:/vectorData/qdrant`, 컬렉션 `pdf_chunks`

---

## 2026-07-17 (v15) — 순번 20 인제스트 A Locked 완료

**변경 파일**: Docs/20260717_LangGraph-Agentic-backend_인제스트A_Locked_계획.md, Docs/20260715_FAQ_PDF모드_LangGraph분리_계획.md, README.md

**변경 내용**: 순번 20 — PDF 인제스트를 **일방향 A로 Locked** 하고 로컬 MVP 파이프라인(1~20)을 닫음

- README §4·§8·§9와 원본 분리 계획서의 Open을 Locked A로 맞춤
- Agentic 인제스트(B)는 순번 19 샘플 확보 후에만 재개
- 보류 유지: 순번 9 실임베딩 · 순번 19 표/스캔 품질

---

## 2026-07-17 (v14) — 순번 19 품질 샘플 보류

**변경 파일**: Docs/20260717_LangGraph-Agentic-backend_품질샘플_계획.md, README.md

**변경 내용**: 순번 19 — 표/스캔 PDF 실물 샘플이 없어 품질 검증을 **보류**

- 재개 조건: 표·스캔 각 1종 확보 후 추출·검색 품질 기록
- 다음: 순번 20 인제스트 A Locked

---

## 2026-07-17 (v13) — 순번 18 인제스트 A/B 비교 완료

**변경 파일**: Docs/20260717_LangGraph-Agentic-backend_인제스트AB비교_계획.md, README.md

**변경 내용**: 순번 18 — 인제스트 A(일방향) vs B(Agentic) 비교 결과, 로컬 MVP는 **A 유지**로 결론

- 검색 Agentic(Locked)은 A 연료로 Tool·`/agent/chat`까지 이미 통과
- B는 표/스캔·OCR 병목이 생길 때 재개 (순번 19 샘플 필요)
- 다음: 순번 19 품질 샘플 → 20 Locked

---

## 2026-07-17 (v12) — 순번 17 UI PDF 연동 완료

**변경 파일**: app/main.py, frontend_react/src/App.jsx, frontend_react/.env.development, frontend_react/.env.sample, Docs/20260717_LangGraph-Agentic-backend_UI_PDF연동_계획.md, README.md

**변경 내용**: 순번 17 — 챗봇 UI의 PDF 채널이 LangGraph `POST /agent/chat`로 질문하도록 연결

- ChatHeader `[FAQ]`/`[PDF]` · CORS · `REACT_APP_AGENT_API_URL`(기본 `:8005`)
- FAQ는 기존 `:9000` 유지, PDF만 에이전트 백엔드 호출
- 다음: 순번 18 인제스트 A vs B 비교

---

## 2026-07-17 (v11) — 순번 15~16 /agent/chat 완료

**변경 파일**: app/schemas/agent.py, app/api/agent.py, app/graph/runtime.py, app/main.py, tests/test_agent_api.py, README.md

**변경 내용**: 순번 15~16 — `POST /agent/chat`가 `answer`+`citations` 계약을 지키도록 구현·테스트 통과

- 운영은 Groq+Qdrant(`runtime.run_agent_chat`), 테스트는 runner Depends override
- 다음: 순번 17 UI PDF 모드 연동

---

## 2026-07-17 (v10) — 순번 14 Tool 2회 완료

**변경 파일**: tests/test_graph_workflow.py, README.md

**변경 내용**: 순번 14 — Tool 2회(1차 부족 → 재검색 → 종합 답변) 시나리오 통과

- `tool_call_count == 2`, 검색 쿼리 2회·citations 누적 검증
- 다음: 순번 15~16 `/agent/chat` API

---

## 2026-07-17 (v9)

**변경 파일**: README.md (§1)

**변경 내용**: 전체 작업순서도를 티스토리와 같은 **단일 표**(상태|순번|작업)로 README 맨 앞에 둠

- 처음부터 끝까지 순번 1~20, 상태 칸 맨 앞 (`[ ]`/`[보류]`/`[완료]`)
- **다음 = 순번 14 Tool 2회**

---

## 2026-07-17 (v8) — Phase 1 Tool 1회 완료

**변경 파일**: app/graph/nodes.py, app/graph/workflow.py, tests/test_graph_workflow.py, Docs/20260717_LangGraph-Agentic-backend_Phase1_Tool1_계획.md

**변경 내용**: Phase 1 — Tool 1회(문서 질문 → 검색 1번 → 재판단 → 답변) 시나리오 통과

- `tool_call_count == 1`, citations·answer 검증, 검색 상한(`MAX_TOOL_CALLS=3`)으로 무한 루프 방지
- Tool 2회·`/agent/chat`는 다음 단계 (`pytest` 17건 통과)

---

## 2026-07-17 (v7) — Groq LLM 연결 완료

**변경 파일**: app/graph/groq_decision.py, app/graph/workflow.py, app/config.py, tests/test_groq_decision.py, Docs/20260717_LangGraph-Agentic-backend_Groq연결_계획.md

**변경 내용**: 검색 판단 노드에 Groq를 연결 — `need_search` / `search_query` / `answer` JSON 판단

- `make_groq_decide_fn` · `build_groq_agent_graph` 추가 (`.env`의 `GROQ_API_KEY` 사용)
- 파싱·mock 호출 단위 테스트로 API 키 없이 검증
- Tool 1회(검색 실행 후 재판단)는 다음 단계

---

## 2026-07-17 (v6) — Phase 1 Tool 0회 완료

**변경 파일**: app/graph/state.py, app/graph/nodes.py, app/graph/workflow.py, tests/test_graph_workflow.py, tests/test_search_documents.py, Docs/20260717_LangGraph-Agentic-backend_Phase1_Tool0_계획.md

**변경 내용**: Phase 1 — LangGraph 골격과 Tool 0회(검색 불필요) 시나리오 통과

- `llm_decision → final_answer` 경로에서 `tool_call_count == 0`, Tool 미호출을 TDD로 확인
- `search_documents` 단위 테스트 추가, 판단은 `decide_fn` 주입(실 LLM 아직 없음)
- Tool 1회·2회·`/agent/chat`는 다음 단계 (`pytest` 10건 통과)

---

## 2026-07-17 (v5) — 본 코드 인제스트 진입점 완료

**변경 파일**: ingest/index_documents.py, tests/test_ingest.py, data/uploads/.gitkeep, .gitignore, Docs/20260717_LangGraph-Agentic-backend_업로드경로_계획.md

**변경 내용**: 본 코드에 업로드→`data/uploads/`→로드·청킹·Qdrant 진입점을 두고 테스트는 검증만 하도록 정리

- `store_upload` / `ingest_pdf`를 `index_documents.py`에 추가 (uploads 밖 경로 거부)
- E2E 테스트는 fixture를 업로드 소스로만 쓰고 본 코드 파이프라인을 호출
- `data/uploads/` 폴더와 업로드 PDF `.gitignore` 규칙 추가 (`pytest` 7건 통과)

---

## 2026-07-17 (v4)

**변경 파일**: README.md, CHANGELOG.md

**변경 내용**: PDF 실경로 원칙을 Locked로 문서화 — 업로드 → `data/uploads/` → 로드·청킹·Qdrant

- 본 코드만 `data/uploads/원본.pdf` 경로를 쓰고, `tests/fixtures`는 검증용 가짜 입력으로 둔다
- 테스트가 인제스트 파이프라인을 “대신 조립”하거나 fixture가 앱의 유일한 경로가 되면 안 된다고 README §1·§7에 명시
- 업로드 API·저장 폴더는 아직 미구현(이후 Phase). 구조 트리에 `data/uploads/`를 기준안으로 추가

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
