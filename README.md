# LangGraph-Agentic-backend

> 환경: 로컬 학습/개발 우선
> 역할: PDF 모드 전용 LangGraph Agentic API 서버
> 기준: FAQ 벡터(`qa_*`)와 PDF 벡터를 분리하고, PDF 사용자 검색은 LangGraph Tool 루프로 처리

---

## 1. 전체 폴더 구조

현재는 README와 CHANGELOG 착수 단계이며, 아래 구조는 Phase 1 구현 시점의 기준안이다.

```text
LangGraph-Agentic-backend/
├── app/                         # FastAPI 애플리케이션
│   ├── main.py                  # /agent/chat 엔드포인트 진입점
│   ├── api/
│   │   └── agent.py             # 요청/응답 라우터
│   ├── graph/
│   │   ├── state.py             # LangGraph State 타입
│   │   ├── nodes.py             # LLM 판단 노드, Tool 실행 노드
│   │   └── workflow.py          # StateGraph 구성
│   ├── tools/
│   │   └── search_documents.py  # PDF 문서 검색 Tool
│   ├── schemas/
│   │   └── agent.py             # request/response 모델
│   └── config.py                # 환경변수 로딩
│
├── ingest/                      # Phase 0.5: PDF 로드/청킹/임베딩
│   ├── load_pdf.py              # PDF 로더
│   ├── chunk.py                 # 청킹 규칙
│   └── index_documents.py       # Vector Store 적재 스크립트
│
├── tests/                       # TDD 테스트
│   ├── test_search_documents.py
│   ├── test_graph_workflow.py
│   └── test_agent_api.py
│
├── docs/                        # 구현 중 보조 문서(필요 시)
├── .env.example                 # 환경변수 예시
├── pyproject.toml               # Python 패키지/테스트 설정
└── README.md
```

**구분 기준**
- `app/` → 상시 실행되는 Agentic API 서버
- `ingest/` → PDF 인덱스를 준비하는 별도 스크립트 영역
- `tests/` → Tool 0회/1회/2회, API 계약, 회귀 테스트
- `docs/` → 구현 중 추가 결정이 필요한 보조 문서

---

## 2. 서비스별 상세 (포트 · 역할 · 사용 언어 · 개발/서드파티)

| 서비스/모듈 | 포트 | 동작 방식 | 역할 | 주 사용 언어/스택 | 구분 |
|---|---:|---|---|---|---|
| `agent-api` | 8005(가안) | 상시서버 | `POST /agent/chat` 제공, LangGraph 실행 진입점 | Python, FastAPI | 개발 |
| `agent-graph` | - | 내부 그래프 | LLM 판단 → Tool 호출 → Observation → 최종 답변 | Python, LangGraph, LangChain 계열 | 개발 |
| `search_documents` | - | Tool | PDF Vector Store 검색, citation 근거 반환 | Python, Vector DB client | 개발 |
| `pdf-ingest` | - | 스크립트/배치 | PDF 로드 → 청킹 → 임베딩 → Vector Store 적재 | Python, PDF loader, embedding client | 개발 |
| `vector-store` | 6333(가안) | 외부 인프라 | PDF 청크 임베딩 저장소 | Qdrant 또는 동등 Vector DB | 서드파티 |
| `llm-provider` | - | 외부 API | Tool 필요 여부 판단, 최종 답변 생성 | Groq/Gemini/OpenAI 등 | 서드파티 |

---

## 3. LangGraph / LangChain 적용 범위 (확정)

```text
FAQ 검색 경로                → 이 프로젝트에서 구현하지 않음 (기존 backend_python 유지)
PDF 인제스트                → Open: Default는 일방향/규칙 기반
PDF 사용자 검색(query)      → LangGraph 핵심 사용 구간
프론트엔드 FAQ/PDF 버튼     → 이 프로젝트에서 구현하지 않음 (기존 UI에서 연동)
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

## 4. 레이어 ↔ 서비스 매핑

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

## 5. 표준 인터페이스 규약

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

## 6. 환경변수 규약 (`.env`)

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

# Vector Store (가안)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=pdf_chunks
```

---

## 7. 현재 결정 상태

| 구분 | 결정 | 상태 |
|---|---|---|
| 프로젝트 분리 | PDF 모드용 LangGraph backend를 별도 레포로 둔다 | Locked |
| API 진입점 | `POST /agent/chat` | Locked |
| 사용자 검색 | LLM 판단 → Tool → Observation → 재판단 → 답변 | Locked |
| FAQ/PDF 벡터 | FAQ `qa_*`와 PDF 청크를 섞지 않는다 | Locked |
| 인제스트 | 일방향/규칙 기반 A vs Agentic B | Open |
| 인제스트 기본안 | Phase 0.5에서는 A로 인덱스만 준비 | Default |

---

## 8. 개발 순서

### Phase 0.5 — 인제스트 Default A

1. 샘플 PDF 로드
2. 청킹
3. 임베딩
4. Vector Store 적재

목적은 인제스트 방식을 확정하는 것이 아니라, Phase 1 검색 Agentic 구현에 필요한 검색 연료를 준비하는 것이다.

### Phase 1 — 검색 Agentic

1. `search_documents` Tool 단위 테스트
2. Tool 0회 시나리오: 검색 불필요 질문
3. Tool 1회 시나리오: 문서 질문 → 검색 → 답변
4. Tool 2회 시나리오: 1차 검색 부족 → 재검색 → 종합 답변
5. `/agent/chat` HTTP 계약 테스트
6. 기존 UI의 PDF 모드와 연동

### Phase 2 — 인제스트 실험

1. A(일방향/규칙)와 B(Agentic 인제스트) 비교
2. 표/스캔 PDF 등 품질 차이가 나는 샘플로 검증
3. 효과가 크면 B를 Locked, 아니면 A를 Locked

---

## 9. 검증 체크리스트

- [ ] PDF 검색 경로가 단순 `retriever → LLM`이 아니라 LangGraph Tool 루프인지 로그로 확인
- [ ] Tool 0회/1회/2회 테스트가 통과
- [ ] `/agent/chat` 응답이 `answer`와 `citations` 계약을 지킴
- [ ] PDF 청크가 FAQ `qa_*` 컬렉션에 들어가지 않음
- [ ] 인제스트 A/B가 아직 미결정이라는 상태가 문서에 유지됨

---

## 10. 원본 계획 문서

이 README는 아래 두 문서를 바탕으로 새 레포용으로 요약 정리했다.

- `Docs/20260715_FAQ_PDF모드_LangGraph분리_계획.md`
- `Docs/20260715_RAG_Agent_다이어그램_부록.md`

---

## 11. 한 줄 요약

`LangGraph-Agentic-backend`는 PDF 사용자 검색을 LangGraph 기반 Agentic Tool 루프로 구현하기 위한 별도 백엔드 프로젝트다.
