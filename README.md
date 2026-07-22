# LangGraph-Agentic-backend

> 환경: 로컬 학습/개발 우선  
> 역할: PDF 모드 전용 LangGraph Agentic API 서버  
> 기준: FAQ 벡터(`qa_*`)와 PDF 벡터를 분리하고, PDF 사용자 검색은 LangGraph Tool 루프로 처리

---

## 1. 전체 작업순서도 (처음부터 끝까지, 파이프라인 기준)

**진행 현황은 여기만 본다.** (CHANGELOG `vN`은 날짜 기록일 뿐, 아래 순번과 무관)

상태: `[ ]` 미완료 · **[보류]** · `[완료]` 완료 · `[]` 결번  
검증: `자동` = pytest로 충분 · `H` = 직접 확인(실키·UI·품질·배포) · `-` = 문서/원칙(별도 테스트 없음)

**다음:** **24**(배포 기동·`/health`·PDF `/agent/chat`) · 순번 25는 **배포 완료 후**  
※ PDF Agent 임베딩 **bge-m3** (`pdf_chunks_bge`). FAQ Chroma bge-m3 교체는 **포기**(MiniLM 유지).  
※ 지표·MBTI·한마디 결론: `Docs/20260720_…내용평가…계획.md` / 실임베딩: `Docs/20260720_순번21_bge-m3_실임베딩_계획.md`  
※ **PDF 안 이솝 vs ARKK** 분기·ARKK ingest: `Docs/20260721_PDF모드_도메인라우터_ARKK_ingest_계획.md` (§4-1) · **완료**


| 검증 | 상태 | 순번 | 작업 |
|------|------|------|------|
| - | [완료] | 1 | 레포·README·CHANGELOG 착수 (PDF 모드 LangGraph 백엔드 분리) |
| 자동 | [완료] | 2 | FastAPI 뼈대 (`pyproject.toml`, `app/main.py`, `app/config.py`, `.env.example`) |
| 자동 | [완료] | 3 | `GET /health` TDD (`tests/test_health.py`) |
| H | [완료] | 4 | 로컬 실행 확인 (`pip install -e ".[dev]"` → `pytest` → `python -m app.main`) |
| 자동 | [완료] | 5 | PDF 로드·청킹 (`ingest/load_pdf.py`, `ingest/chunk.py`) |
| 자동 | [완료] | 6 | FakeEmbedding + Qdrant `pdf_chunks` 적재 (`ingest/index_documents.py`)  |
| 자동 | [완료] | 7 | 실경로: 업로드 → `data/uploads/` → `store_upload` / `ingest_pdf` |
| - | [] | 8 | **결번** (실경로는 순번 7·`data/uploads`에 흡수) |
| - | [] | 9 | **결번** |
| 자동 | [완료] | 10 | `search_documents` Tool 단위 테스트  |
| 자동 | [완료] | 11 | LangGraph 골격 + Tool 0회 (검색 불필요 → 최종 답변) 즉 Tool을 한 번도 안 부르는 경우입니다.|
| H | [완료] | 12 | Groq 판단 연결 (`app/graph/groq_decision.py`, `.env` `GROQ_API_KEY`) |
| H | [완료] | 13 | Tool 1회 (문서 질문 → 검색 → 재판단 → 답변) + `MAX_TOOL_CALLS=3` |
| H | [완료] | 14 | Tool 2회 (1차 검색 부족 → 재검색 → 종합 답변) |
| 자동 | [완료] | 15 | `POST /agent/chat` 요청/응답 계약 (`answer` + `citations`) |
| 자동 | [완료] | 16 | HTTP 계약 테스트 (`tests/test_agent_api.py`) |
| H | [완료] | 17 | 기존 챗봇 UI PDF 모드 → 이 백엔드 `/agent/chat` 연동 |
| H | [완료] | 18 | 인제스트 A(일방향) vs B(Agentic) 비교 실험 |
| H | **[보류]** | 19 | 표/스캔 PDF 등 품질 샘플 검증 |
| - | [완료] | 20 | 인제스트 A Locked 확정 + README/CHANGELOG 반영 |
| H | [완료·품질확인중] | 21 | FakeEmbed → 실임베딩(`bge-m3`, `pdf_chunks_bge`, 테스트 3편). **유사도 품질 H 확인** 후 분기(§1-1). FAQ Chroma bge-m3는 **포기** |
| H | [ ] | 21b | **(21 이후·조건부)** 유사도가 애매/낮으면 FAQ와 같이 **유사도 + 키워드매칭 합산** 이식. bge-m3만으로 충분하면 **스킵** |
| H | [완료] | 22 | **배포 전** — `Dockerfile` + `.dockerignore` (`app`/`ingest`만 이미지에 넣고 `tests/` 제외) |
| H | [완료] | 23 | **배포 전** — compose/환경변수 운영 규약 (`APP_PORT=8010`, `QDRANT_*`, `GROQ_*`) |
| H | [ ] | 24 | **배포** — 서버(또는 compose) 기동 후 `GET /health` · PDF `/agent/chat` 확인 |
| H | [ ] | 25 | **배치 인제스트 + 입력단** — 우화 312편 등. **배포(22→24) 완료 후** (업로드 UI와 같이) |
| 자동 | [완료] | 26 | **ARKK ingest** — holdings PDF → bge-m3 → Qdrant `arkk_holdings_bge` (우화 컬렉션 분리) |
| H | [완료] | 27 | **PDF 도메인 라우터** — LLM이 이솝 vs ARKK 먼저 판별 → 이솝만 규칙 라우터, ARKK는 holdings 벡터 직행 |

---

## 1-1. 작업순서도 세부 설명

순번 2 설명 ---------------------------------------------------------
**FastAPI 뼈대**에서 만든 것 (아직 Agent/PDF 기능 없이, 서버 틀만 잡은 단계):

| 파일 | 역할 |
|------|------|
| `pyproject.toml` | 이 폴더가 Python 프로젝트다, 쓸 패키지는 이거다 |
| `app/main.py` | FastAPI 앱 진입점 (서버 켜는 문) |
| `app/config.py` | 포트·API 키 등 설정 읽는 곳 |
| `.env.example` | 설정 예시 (실제 비밀값은 `.env`) |

순번 4 설명 ---------------------------------------------------------
-e : editable — 코드 고쳐도 다시 설치 안 해도 됨
pip install -e ".[dev]" = 이 프로젝트를 개발 모드로 설치하라는 명령입니다.
	
[dev] : 테스트용 추가 패키지(pytest, httpx 등)도 같이

순번 6 :  pytest tests/test_ingest_local_qdrant.py -v -s
순번 10 : pytest tests/test_search_documents.py -v
순번 11 : pytest tests/test_graph_workflow.py -v
   사용자 질문 → LLM 판단: "문서 검색 필요 없음"
             → Tool(search) 호출 0회
             → 바로 최종 답변

순번 5 설명 ---------------------------------------------------------
# chunk_size / overlap = 글자 수 (토큰 아님). 문서 종류별은 아직 미적용.
# 후보: manual 500/100, contract 800/150
# 현재 기본: 300/60 + Separator 우선 (문단·줄·문장부호 .?!。 → 공백 → hard cut)
# 이솝 우화 분석 카드: 점수·키워드→metadata, 원문/한마디 결론→본문 청크 분리(content_type=origin|modern)
#   상세: Docs/20260719_LangGraph-Agentic-backend_우화메타데이터청킹_계획.md
# 표/리스트 경계는 보존하지 않음 → 순번 19에서 다룸
# 청킹 방식·크기를 바꾼 뒤에는 pdf_chunks 재인제스트 필수
#   절차: 컬렉션 비우기(또는 삭제) → 동일 PDF를 다시 ingest_pdf
# 상세: Docs/20260718_LangGraph-Agentic-backend_청킹품질_계획.md
Args:
           pages: load_pdf_pages 결과
   300     chunk_size: 청크 최대 글자 수
   60      chunk_overlap: 인접 청크 겹침 글자 수

순번 21 · 21b 설명 — 실임베딩 이후 유사도 -----------------------
**지금( FakeEmbed )은 유사도 UI·합산을 결정하지 않는다.** UI는 PDF 모드에서 `0.000` 고정일 수 있음 → 표시 연동은 21 이후.

```
순번 21 결과 확인 (H)
  ├─ bge-m3 유사도만으로 충분히 잘 걸러짐
  │     → 벡터 유사도 그대로 사용 (API score 노출·UI 표시)
  │     → 순번 21b 스킵
  └─ 유사도가 애매하게/낮게 나옴 (FAQ 때처럼)
        → 유사도 + 키워드매칭 합산 방식을 FAQ에서 이식 (순번 21b)
```

- metadata 질문(내용평가·키워드 등)은 검색을 안 타므로 **유사도 해당 없음** (되묻기/모름과 구분). 상세: `Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md`
- FAQ Chroma `bge-m3` 교체: **포기** (하드코딩·품질보정(threshold/키워드합산) 재검증 부담). FAQ는 MiniLM 유지


## 2. 전체 폴더 구조

현재: 순번 1~7·10~18·20·22·23 `[완료]`, 8·9 **[결번]**, 19 **[보류]** — **다음 24 기동 확인** · 21b 조건부

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
│   │   ├── workflow.py          # StateGraph + build_groq_agent_graph
│   │   └── domain_router.py     # 이솝 vs ARKK LLM 분류
│   ├── metrics/                 # 내용평가·키워드 등 metadata 라우팅
│   ├── tools/
│   │   ├── search_documents.py  # PDF 문서 검색 Tool (이솝 pdf_chunks_bge)
│   │   ├── search_holdings.py   # ARKK arkk_holdings_bge 검색
│   │   └── lookup_fable_metadata.py
│   └── schemas/
│       └── agent.py             # request/response (+ session_id)
│
├── ingest/                      # P0.5: PDF 로드/청킹/임베딩
│   ├── load_pdf.py              # PDF 로더 (pypdf)
│   ├── chunk.py                 # Separator 우선 청킹 300/60 (Default A)
│   ├── fable_parse.py           # 이솝 우화 카드 → metadata + 원문/현대 분리
│   ├── index_documents.py       # store_upload / ingest_pdf / Qdrant 적재
│   ├── arkk_manifest.yaml       # ARKK holdings manifest (1건)
│   ├── holdings_metadata.py     # fund·as_of_date 청크 메타
│   └── ingest_arkk.py           # holdings 전용 ingest
│
├── scripts/
│   ├── reingest_three_fables.py # 우화 3편 bge-m3 재인제스트
│   └── ingest_arkk_holdings.py  # ARKK PDF → arkk_holdings_bge
│
├── data/
│   └── uploads/                 # 업로드된 원본 PDF 저장 (실경로 Locked)
│       └── ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf  # ARKK 원본 (수동 복사)
│
├── tests/                       # TDD 테스트 (검증만 — 실경로가 아님)
│   ├── fixtures/sample.pdf      # 테스트용 가짜 입력
│   ├── test_health.py           # P0: /health
│   ├── test_ingest.py           # P0.5: 로드·청킹·인덱싱·검색 (:memory:)
│   ├── test_ingest_local_qdrant.py  # 순번6: store_upload→ingest→로컬 Qdrant (운영과 동일 규칙)
│   ├── test_chunk_quality.py    # 청킹 품질 (문장부호·overlap)
│   ├── test_fable_metadata.py   # 우화 카드 metadata / origin·modern
│   ├── test_arkk_holdings_ingest.py  # ARKK 메타·payload
│   ├── test_search_documents.py # P1: Tool 단위
│   ├── test_graph_workflow.py   # P1: Tool 0/1회
│   └── test_agent_api.py        # (P1-API)
│
├── docs/                        # 구현 중 보조 문서(필요 시)
├── Dockerfile                   # 순번 22: 배포 이미지 (app/ingest)
├── .dockerignore                # 빌드 context에서 tests·.env 등 제외
├── .env.example                 # 로컬 환경변수 예시
├── .env.hetzner.example         # Hetzner compose용 예시 (시크릿은 .env.hetzner)
├── pyproject.toml               # Python 패키지/테스트 설정
└── README.md
```

**구분 기준**
- `app/` → 상시 실행되는 Agentic API 서버
- `ingest/` → PDF 인덱스를 준비하는 별도 스크립트 영역 (우화 `fable_parse` / ARKK `holdings_metadata`·`ingest_arkk` 분리)
- `scripts/` → 배치·재인제스트 CLI (`reingest_three_fables`, `ingest_arkk_holdings` 예정)
- `data/uploads/` → 사용자가 올린 원본 PDF 실저장 경로
- `tests/` → 본 코드를 검증만 함 (앱이 의존하는 실경로가 아님)
- `Dockerfile` / `.dockerignore` → Hetzner compose build용 (순번 23에서 스택 연결)
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
| `agent-api` | 8010 | 상시서버 | `POST /agent/chat` 제공, LangGraph 실행 진입점 | Python, FastAPI | 개발 |
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

### PDF 사용자 검색 그래프 (Locked — Tool 루프)

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

### 4-1. PDF 모드 도메인 라우터 (순번 26→27, 착수 예정)

**지금(운영)**: PDF 질문 → **이솝 규칙 라우터**(목록·제목·평가·MBTI…) → 안 걸리면 `pdf_chunks_bge` 검색 + 위 Tool 루프.  
**문제**: ARKK(주식지표) 질문이 우화 규칙에 먼저 걸릴 수 있음.  
**목표**: PDF 모드 **안에서만** 도메인 LLM이 **이솝 vs ARKK**를 먼저 고른다. UI에 FAQ/PDF/주식 3버튼은 두지 않는다.

```text
PDF 모드 질문
  → ② 도메인 LLM: 이솝우화 | 주식지표(ARKK)
      ├─ 이솝 → ① 기존 규칙 라우터 → pdf_chunks_bge + Tool 루프
      └─ ARKK  → arkk_holdings_bge 벡터 검색 (규칙 없음) + LLM
```

| Qdrant 컬렉션 | 내용 | 임베딩 |
|---|---|---|
| `pdf_chunks_bge` | 이솝 우화 PDF 청크 | bge-m3 (운영 중) |
| `arkk_holdings_bge` | ARK ETF holdings PDF | bge-m3 (순번 26) |

**순번 26 파일 트리** (상세·체크리스트는 계획서):

```text
data/uploads/ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf
ingest/arkk_manifest.yaml · holdings_metadata.py · ingest_arkk.py
scripts/ingest_arkk_holdings.py
tests/test_arkk_holdings_ingest.py
```

- FAQ 모드(`qa_*` / Chroma)는 이 분기와 **무관** (탭으로 이미 분리).
- 상세·체크리스트: `Docs/20260721_PDF모드_도메인라우터_ARKK_ingest_계획.md`
- LangGraph 학습용 `5_0_RAG.py` / `5_3_Agentic_RAG.py`는 MiniLM + `langgraph_arkk_pdf` — **참고만**, 운영 ingest는 Agentic-backend에서 bge-m3로 별도 적재.

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
  "question": "육아휴직 기간은 어떻게 되나요?",
  "session_id": "optional-chat-session-id"
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
  ],
  "mbti": "INFP"
}
```

**원칙**
- `answer`는 사용자에게 보여줄 최종 답변이다.
- `citations`는 PDF 검색 근거이며, 비어 있으면 검색 근거가 없음을 의미한다.
- `session_id`가 있으면 직전 우화 제목·MBTI를 단기 메모리에 둔다. `mbti`는 현재 세션 값(없으면 `null`).
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
APP_PORT=8010

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
QDRANT_COLLECTION=pdf_chunks_bge
QDRANT_COLLECTION_ARKK=arkk_holdings_bge
```

### Hetzner (`docker-compose.hetzner.yml`, 순번 23)

| 항목 | 규약 |
|------|------|
| 서비스 | `langgraph_agentic` (context `./LangGraph-Agentic-backend`) · `qdrant` |
| 포트 | `8010` (Agent) · `6333` (Qdrant, localhost 바인드) |
| env 파일 | `LangGraph-Agentic-backend/.env.hetzner` (시크릿) · 예시는 `.env.hetzner.example` |
| Qdrant | compose가 `QDRANT_PATH=` 비움 · `QDRANT_HOST=qdrant` · `QDRANT_PORT=6333` |
| 호스트 경로 | `/home/chatbot/qdrant`, `/home/chatbot/agentic_uploads` |
| 레거시 | `regline_hub`(:3003) 제거 — 허브는 Vercel |

기동·`/health` 확인은 **순번 24**. CPX22(4GB)에서 bge-m3+Qdrant 동시 기동은 OOM 주의.

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
| 인제스트 | 로드 → Separator 우선 청킹(300/60) → 임베딩 → Qdrant (`ingest/`) | **Locked A** |
| 청킹 변경 후 | `pdf_chunks` 비우기 → 동일 PDF 재인제스트 (옛/새 청크 혼재 방지) | 운영 필수 |
| Qdrant 연결 | `QDRANT_PATH` 로컬 우선, 비면 `HOST:PORT`(Docker) | Locked |
| PDF 도메인 | 이솝 vs ARKK LLM 판별 후 이솝만 규칙 라우터 | **예정** (순번 27) |
| ARKK 벡터 | `arkk_holdings_bge` — 우화 `pdf_chunks_bge`와 분리 | **예정** (순번 26) |

---

## 9. 검증 체크리스트

- [x] PDF 검색 경로가 단순 `retriever → LLM`이 아니라 LangGraph Tool 루프인지 로그로 확인 (Tool 0/1/2)
- [x] Tool 0회/1회/2회 테스트가 통과
- [x] `/agent/chat` 응답이 `answer`와 `citations` 계약을 지킴
- [x] PDF 청크가 FAQ `qa_*`가 아닌 별도 컬렉션 `pdf_chunks`에 적재됨 (Phase 0.5)
- [x] 인제스트 **A Locked** (순번 18 비교 → 순번 20 확정; B는 순번 19 보류 후 재개)

---

## 10. 원본 계획 문서

이 README는 아래 문서를 바탕으로 새 레포용으로 요약 정리했다.

- `Docs/20260715_FAQ_PDF모드_LangGraph분리_계획.md`
- `Docs/20260715_RAG_Agent_다이어그램_부록.md`
- `Docs/20260721_PDF모드_도메인라우터_ARKK_ingest_계획.md` (순번 26→27)
- `Docs/20260718_고전원문_MBTI현대재해석_컨셉.md` (별도 제품 후보 · 본 README와 구현 무관)

---

## 11. 한 줄 요약

`LangGraph-Agentic-backend`는 PDF 사용자 검색을 LangGraph Agentic Tool 루프로 처리하고, PDF 인제스트는 일방향(A)으로 Locked한 별도 백엔드다.
