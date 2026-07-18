# LangGraph-Agentic-backend

> 환경: 로컬 학습/개발 우선  
> 역할: PDF 모드 전용 LangGraph Agentic API 서버  
> 기준: FAQ 벡터(`qa_*`)와 PDF 벡터를 분리하고, PDF 사용자 검색은 LangGraph Tool 루프로 처리

---

## 1. 전체 작업순서도 (처음부터 끝까지, 파이프라인 기준)

**진행 현황은 여기만 본다.** (CHANGELOG `vN`은 날짜 기록일 뿐, 아래 순번과 무관)

상태: `[ ]` 미완료 · **[보류]** · `[완료]` 완료

**다음:** 로컬 MVP 파이프라인 **완료** (**보류**: 순번 9 실임베딩 · 순번 19 표/스캔 샘플)

| 상태 | 순번 | 작업 |
|------|------|------|
| [완료] | 1 | 레포·README·CHANGELOG 착수 (PDF 모드 LangGraph 백엔드 분리) |
| [완료] | 2 | FastAPI 뼈대 (`pyproject.toml`, `app/main.py`, `app/config.py`, `.env.example`) |
| [완료] | 3 | `GET /health` TDD (`tests/test_health.py`) |
| [완료] | 4 | 로컬 실행 확인 (`pip install -e ".[dev]"` → `pytest` → `python -m app.main`) |
| [완료] | 5 | PDF 로드·청킹 (`ingest/load_pdf.py`, `ingest/chunk.py`) |
| [완료] | 6 | FakeEmbedding + Qdrant `pdf_chunks` 적재 (`ingest/index_documents.py`) |
| [완료] | 7 | 실경로: 업로드 → `data/uploads/` → `store_upload` / `ingest_pdf` |
| [완료] | 8 | 테스트는 `tests/fixtures`를 업로드 **소스**로만 쓰고 본 코드 검증 |
| **[보류]** | 9 | 실임베딩(OpenAI/Google 등)으로 FakeEmbedding 교체 |
| [완료] | 10 | `search_documents` Tool 단위 테스트 |
| [완료] | 11 | LangGraph 골격 + Tool 0회 (검색 불필요 → 최종 답변) |
| [완료] | 12 | Groq 판단 연결 (`app/graph/groq_decision.py`, `.env` `GROQ_API_KEY`) |
| [완료] | 13 | Tool 1회 (문서 질문 → 검색 → 재판단 → 답변) + `MAX_TOOL_CALLS=3` |
| [완료] | 14 | Tool 2회 (1차 검색 부족 → 재검색 → 종합 답변) |
| [완료] | 15 | `POST /agent/chat` 요청/응답 계약 (`answer` + `citations`) |
| [완료] | 16 | HTTP 계약 테스트 (`tests/test_agent_api.py`) |
| [완료] | 17 | 기존 챗봇 UI PDF 모드 → 이 백엔드 `/agent/chat` 연동 |
| [완료] | 18 | 인제스트 A(일방향) vs B(Agentic) 비교 실험 |
| **[보류]** | 19 | 표/스캔 PDF 등 품질 샘플 검증 |
| [완료] | 20 | 인제스트 A Locked 확정 + README/CHANGELOG 반영 |

---

## 2. 전체 폴더 구조

현재: 순번 1~8·10~18·20 `[완료]`, 9·19 **[보류]** — **로컬 MVP 파이프라인 종료**.

```text
LangGraph-Agentic-backend/
├── app/                         # FastAPI 애플리케이션
│   ├── main.py                  # 앱 진입점 (Phase 0: /health)
│   ├── config.py                # 환경변수 로딩 (QDRANT_PATH 포함)
│   ├── qdrant_factory.py        # 로컬 PATH / HOST:PORT 클라이언트 생성
│   ├── api/
│   │   └── agent.py             # 요청/응답 라우터 (P1-API)
│   ├── graph/                   # P1: LangGraph (검색 판단)
│   │   ├── state.py             # Agent State
│   │   ├── nodes.py             # 판단·Tool·최종답 노드
│   │   ├── groq_decision.py     # Groq LLM 판단 (decide_fn)
│   │   └── workflow.py          # StateGraph + build_groq_agent_graph
│   ├── tools/
│   │   └── search_documents.py  # PDF 문서 검색 Tool
│   └── schemas/
│       └── agent.py             # request/response 모델
│
├── ingest/                      # P0.5: PDF 로드/청킹/임베딩
│   ├── load_pdf.py              # PDF 로더 (pypdf)
│   ├── chunk.py                 # 고정 길이 청킹 (Default A)
│   └── index_documents.py       # store_upload / ingest_pdf / Qdrant 적재
│
├── data/
│   └── uploads/                 # 업로드된 원본 PDF 저장 (실경로 Locked)
│
├── tests/                       # TDD 테스트 (검증만 — 실경로가 아님)
│   ├── fixtures/sample.pdf      # 테스트용 가짜 입력
│   ├── test_health.py           # P0: /health
│   ├── test_ingest.py           # P0.5: 로드·청킹·인덱싱·검색
│   ├── test_search_documents.py # P1: Tool 단위
│   ├── test_graph_workflow.py   # P1: Tool 0/1회
│   └── test_agent_api.py        # (P1-API)
│
├── docs/                        # 구현 중 보조 문서(필요 시)
├── .env.example                 # 환경변수 예시
├── pyproject.toml               # Python 패키지/테스트 설정
└── README.md
```

**구분 기준**
- `app/` → 상시 실행되는 Agentic API 서버
- `ingest/` → PDF 인덱스를 준비하는 별도 스크립트 영역
- `data/uploads/` → 사용자가 올린 원본 PDF 실저장 경로
- `tests/` → 본 코드를 검증만 함 (앱이 의존하는 실경로가 아님)
- `docs/` → 구현 중 추가 결정이 필요한 보조 문서

### PDF 경로 원칙 (Locked)

```text
업로드 → data/uploads/원본.pdf 저장
  → load_pdf_pages(그경로)
  → 청킹
  → Qdrant(pdf_chunks)
```

- **본 코드**: `store_upload(소스)` → `ingest_pdf(저장된경로)` (`ingest/index_documents.py`)
- **테스트**(`tests/fixtures/…`)는 업로드 소스용 가짜 입력일 뿐. E2E는 본 코드 `store_upload`→`ingest_pdf`만 호출한다.
- `ingest_pdf`는 `data/uploads/`(또는 주입된 uploads_dir) **밖** 경로를 거부한다.
- HTTP 업로드 API는 아직 없음. 지금은 파일 경로를 `store_upload`에 넘기는 진입점까지.

---

## 3. 서비스별 상세 (포트 · 역할 · 사용 언어 · 개발/서드파티)

| 서비스/모듈 | 포트 | 동작 방식 | 역할 | 주 사용 언어/스택 | 구분 |
|---|---:|---|---|---|---|
| `agent-api` | 8005(가안) | 상시서버 | `POST /agent/chat` 제공, LangGraph 실행 진입점 | Python, FastAPI | 개발 |
| `agent-graph` | - | 내부 그래프 | LLM 판단 → Tool 호출 → Observation → 최종 답변 | Python, LangGraph, LangChain 계열 | 개발 |
| `search_documents` | - | Tool | PDF Vector Store 검색, citation 근거 반환 | Python, Vector DB client | 개발 |
| `pdf-ingest` | - | 스크립트/배치 | PDF 로드 → 청킹 → 임베딩 → Vector Store 적재 | Python, PDF loader, embedding client | 개발 |
| `vector-store` | 6333(가안) | 외부 인프라 | PDF 청크 임베딩 저장소 | Qdrant 또는 동등 Vector DB | 서드파티 |
| `llm-provider` | - | 외부 API | Tool 필요 여부 판단, 최종 답변 생성 | Groq/Gemini/OpenAI 등 | 서드파티 |

---

## 4. LangGraph / LangChain 적용 범위 (확정)

```text
FAQ 검색 경로                → 이 프로젝트에서 구현하지 않음 (기존 backend_python 유지)
PDF 인제스트                → Locked A: 일방향/규칙 기반 (load→chunk→embed→Qdrant)
PDF 사용자 검색(query)      → LangGraph 핵심 사용 구간
프론트엔드 FAQ/PDF 버튼     → frontend_react ChatHeader 연동 완료 (순번 17)
```

### PDF 사용자 검색 그래프 (Locked)

```text
START
  → llm_decision_node
      ├─ 검색 불필요 → final_answer_node → END
      └─ 검색 필요   → tool_node(search_documents)
                      → observation 반영
                      → llm_decision_node 재판단
```

- PDF 사용자 검색은 단순 `retriever → LLM` 일방향으로 끝내지 않는다.
- LLM이 검색 Tool 필요 여부와 재검색 여부를 판단한다.
- Tool 노드는 자체 비즈니스 판단을 하지 않고, 검색 실행과 Observation 반환에 집중한다.

---

## 5. 레이어 ↔ 서비스 매핑

```text
[기존 챗봇 UI]
    ChatHeader: [FAQ] [PDF]
        │
        ├─ [FAQ] → backend_python :9000
        │          기존 FAQ 벡터 qa_* 사용
        │
        └─ [PDF] → LangGraph-Agentic-backend
                   POST /agent/chat
                       │
                       ▼
                   LangGraph Tool 루프
                       │
                       ├─ search_documents
                       │      └─ PDF Vector Store
                       │
                       └─ answer + citations 반환
```

**핵심 경계**
- FAQ `qa_*` 컬렉션에 PDF 청크를 넣지 않는다.
- PDF Vector Store는 FAQ 벡터와 분리한다.
- UI는 내부 LangGraph 루프를 몰라도 된다. `/agent/chat` 계약만 알면 된다.

---

## 6. 표준 인터페이스 규약

### 5.1 HTTP API

#### `POST /agent/chat`

PDF 모드에서 사용자가 보낸 질문을 LangGraph Agentic 검색으로 처리한다.

```json
{
  "question": "육아휴직 기간은 어떻게 되나요?"
}
```

응답:

```json
{
  "answer": "문서 근거를 바탕으로 생성한 답변",
  "citations": [
    {
      "source_file": "sample.pdf",
      "page": 1,
      "snippet": "근거 문장 일부"
    }
  ]
}
```

**원칙**
- `answer`는 사용자에게 보여줄 최종 답변이다.
- `citations`는 PDF 검색 근거이며, 비어 있으면 검색 근거가 없음을 의미한다.
- 내부 Tool 호출 횟수(0회/1회/2회 이상)는 API 소비자가 몰라도 된다.

### 5.2 Vector Document 형식

```json
{
  "page_content": "문서 청크 내용",
  "metadata": {
    "source_file": "sample.pdf",
    "page": 1,
    "chunk_id": "sample-001"
  }
}
```

---

## 7. 환경변수 규약 (`.env`)

```properties
# API 서버
APP_HOST=0.0.0.0
APP_PORT=8005

# LLM Provider
API_SELECT=3
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

GOOGLE_API_KEY=
GOOGLE_MODEL=gemini-2.5-flash

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Vector Store — 로컬 PATH 우선 (Chroma persist / LangGraph QDRANT_PATH 패턴)
# PATH가 있으면 Docker 없이 로컬 폴더. 비우면 HOST:PORT(Docker/서버).
QDRANT_PATH=D:/vectorData/qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=pdf_chunks
```

---

## 8. 현재 결정 상태

| 구분 | 결정 | 상태 |
|---|---|---|
| 프로젝트 분리 | PDF 모드용 LangGraph backend를 별도 레포로 둔다 | Locked |
| API 진입점 | `POST /agent/chat` | Locked |
| 사용자 검색 | LLM 판단 → Tool → Observation → 재판단 → 답변 | Locked |
| FAQ/PDF 벡터 | FAQ `qa_*`와 PDF 청크를 섞지 않는다 | Locked |
| PDF 실경로 | 업로드 → `data/uploads/원본.pdf` → `load_pdf_pages` → 청킹 → Qdrant | Locked |
| 테스트 역할 | `tests/`는 검증만. fixture가 본 코드 실경로를 대체하지 않음 | Locked |
| 인제스트 | 로드 → 고정 길이 청킹 → 임베딩 → Qdrant (`ingest/`) | **Locked A** |
| Qdrant 연결 | `QDRANT_PATH` 로컬 우선, 비면 `HOST:PORT`(Docker) | Locked |

---

## 9. 검증 체크리스트

- [x] PDF 검색 경로가 단순 `retriever → LLM`이 아니라 LangGraph Tool 루프인지 로그로 확인 (Tool 0/1/2)
- [x] Tool 0회/1회/2회 테스트가 통과
- [x] `/agent/chat` 응답이 `answer`와 `citations` 계약을 지킴
- [x] PDF 청크가 FAQ `qa_*`가 아닌 별도 컬렉션 `pdf_chunks`에 적재됨 (Phase 0.5)
- [x] 인제스트 **A Locked** (순번 18 비교 → 순번 20 확정; B는 순번 19 보류 후 재개)

---

## 10. 원본 계획 문서

이 README는 아래 두 문서를 바탕으로 새 레포용으로 요약 정리했다.

- `Docs/20260715_FAQ_PDF모드_LangGraph분리_계획.md`
- `Docs/20260715_RAG_Agent_다이어그램_부록.md`

---

## 11. 한 줄 요약

`LangGraph-Agentic-backend`는 PDF 사용자 검색을 LangGraph Agentic Tool 루프로 처리하고, PDF 인제스트는 일방향(A)으로 Locked한 별도 백엔드다.
