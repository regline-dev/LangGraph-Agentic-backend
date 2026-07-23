# LangGraph-Agentic-backend CHANGELOG

PDF 모드용 LangGraph Agentic 백엔드 계획·구조·구현 변경 이력.
파일에 버전을 표기하지 않고 이 문서에 누적한다.

---

## 2026-07-23 (v76)

**변경 파일**: pyproject.toml

**변경 내용**: 배포 컨테이너 기동 실패 수정 — PDF multipart 업로드용 `python-multipart` 의존성 추가

- Actions 배포는 SSH·빌드까지 성공했으나 `/pdf/inspect` Form 때문에 앱이 재시작 루프
- `pip install python-multipart` 규약을 pyproject에 고정

---

## 2026-07-23 (v75)

**변경 파일**: Docs/20260723_Hetzner_배포자동화_계획.md, Docs/20260723_배포 자동화 기술_LangGraph-Agentic-backend.md, .github/workflows/deploy-hetzner.yml, tests/test_deploy_workflow.py

**변경 내용**: 순번 24 MVP — `main` push 시 Hetzner `langgraph_agentic` compose 재빌드 + `/health` 스모크 (GitHub Actions)

- 운영·Secrets는 계획서·**기술 문서**에만 · README에는 기술 서술 없음
- **H:** Secrets 등록 후 Actions 1회

---

## 2026-07-23 (v74)

**변경 파일**: Docs/20260723_PDF_일반메타_title_created_date_계획.md, Docs/20260703_PDF-표준-메타데이터_기준표.md, app/pdf_ingest/doc_metadata.py, app/pdf_ingest/analyze.py, ingest/index_documents.py, tests/test_doc_metadata.py, tests/test_pdf_ingest_service.py · admin PdfVector · README.md

**변경 내용**: 표준 §1 — 일반 PDF `title`·`created_date`를 inspect/ingest 응답·Qdrant 청크·`/pdf/vector` 기본 메타에 반영

- PDF Info Title/날짜 → 없으면 파일명 stem · 업로드일(UTC)
- 우화 청크는 카드 `title` 유지 + `created_date` 스탬프 · TDD 통과
- README 2차 표 — **4a~4c** 추가 · **5·6** 상태 갱신 (CHANGELOG 대비 누락분)

---

## 2026-07-23 (v73)

**변경 파일**: app/fable_pdf/keyword_normalize.py, app/fable_pdf/scorer.py, app/pdf_ingest/analyze.py, tests/test_keyword_normalize.py, Docs/20260703_PDF-표준-메타데이터_기준표.md

**변경 내용**: 우화 키워드(`tags`)는 **한글만** — 채점 프롬프트 강화 + `貪欲`→`탐욕` 등 한자 정규화

- 이미 만든 PDF는 **다시 생성·벡터화**해야 화면에 반영 (옛 PDF 본문에 한자가 남아 있음)
- 재벡터화 시 inspect/ingest도 키워드 정규화 적용

---

## 2026-07-23 (v72)

**변경 파일**: Docs/20260703_PDF-표준-메타데이터_기준표.md, Docs/20260723_PDF_일반_메타데이터_기준.md(삭제), Docs/20260723_2차4_…, README.md

**변경 내용**: PDF 메타를 **표준 기준표 한 문서**로 통합 — 위 §1 일반 · 아래 §2 이솝 · §3 ARKK 예약 · 이후 메타 추가는 이 파일만

- 구 `20260723_PDF_일반_메타데이터_기준.md` 삭제 · 파일명 `20260703_PDF-표준-메타데이터_기준표.md`

---

## 2026-07-23 (v71)

**변경 파일**: Docs/20260723_PDF_일반_메타데이터_기준.md, Docs/20260723_2차4_…계획.md (§2-1), README.md

**변경 내용**: PDF **일반 메타데이터 기준** 문서 확정 — 2타입 유지, 일반 필수 키(source·page_count·title·created_date·page·chunk_id)

- ARKK는 이 화면 밖(전용 `as_of_date`) · `section` 보류 · title/created_date 구현은 후속 Phase
- → **v72에서 표준 기준표로 통합·이명**

---

## 2026-07-23 (v70)

**변경 파일**: Docs/20260723_2차4_PDF벡터화_화면_계획.md (§2-1)

**변경 내용**: 일반 PDF **기본 메타**를 문서급·청크급으로 정리 — source/page/chunk_id/title/section/total_pages/created_date

- 필수(지금): `source_file`·`page`·`chunk_id`·`page_count` · title/created_date는 다음 · section은 보류

---

## 2026-07-23 (v69)

**변경 파일**: Docs/20260723_2차4_PDF벡터화_화면_계획.md, app/api/pdf_ingest.py, app/pdf_ingest/*, app/schemas/pdf_ingest.py, tests/test_pdf_ingest_*.py, README.md · admin PdfVector

**변경 내용**: 2차-4 UX — PDF 타입(이솝/일반)·`POST /pdf/inspect`·불일치 모달·완료 화면 벡터결과\|메타 50:50

- 일반 PDF도 **기본 메타**(페이지·파일·글자수) · 이솝 실패 시 「우화 카드 메타 실패」
- 메타 부모 그룹(내용 평가·영상화 적합도) · 다시 하기 오른쪽 하단 · TDD 통과
- H: 이솝/일반/불일치 모달 확인

---

## 2026-07-23 (v68)

**변경 파일**: Docs/20260723_2차4_PDF벡터화_화면_계획.md, app/api/pdf_ingest.py, app/pdf_ingest/*, app/schemas/pdf_ingest.py, app/main.py, tests/test_pdf_ingest_*.py, README.md · admin PdfVector

**변경 내용**: 2차 순번 4 — `POST /pdf/ingest`로 PDF 업로드→`data/uploads`→Qdrant 적재 · 완료 화면에 **문서 메타데이터** 표시

- 어드민 `/pdf/vector` · 파일명 옆 **× 선택 취소** · StepBar 폭 **생성과 동일 80%**
- 동일 파일명 재업로드 시 기존 포인트 삭제 후 재적재 · TDD 통과
- H: 메타·×·바 폭 재확인

---

## 2026-07-23 (v67)

**변경 파일**: Docs/20260722_순번27이후_…계획.md, README.md

**변경 내용**: 2차 순번 3 H 통과 — `/pdf/generate` 원문 1건→PDF 생성·다운로드·미리보기 확인

- 다음: **2차-4** PDF 벡터화 화면 · 입력단 메타·배치·중복처리는 보류

---

## 2026-07-23 (v66)

**변경 파일**: Docs/20260723_…PDF_문서_만들기.md (§12), Docs/20260722_순번27이후_…계획.md

**변경 내용**: 동일 원문 중복 생성 — MVP는 허용(새 번호·재채점), 이후 A~D 후보를 계획서에 기록

- 상세·미결 체크: 20260723 문서 **§12**

---

## 2026-07-23 (v65)

**변경 파일**: Docs/20260723_입력단에서_메타데이터_생성하여_여러_형식의_PDF_문서_만들기.md, Docs/20260722_순번27이후_어드민PDF모드_입력단_계획.md

**변경 내용**: 입력단 메타데이터·멀티 타입 구현은 **보류** — 이솝 `/pdf/generate` 1건 정상 생성이 우선

- 1건(다운로드·미리보기) 통과 후에만 20260723 문서 Phase B 재개

---

## 2026-07-23 (v64)

**변경 파일**: Docs/20260723_입력단에서_메타데이터_생성하여_여러_형식의_PDF_문서_만들기.md

**변경 내용**: 입력단이 메타 스펙을 넘겨 여러 PDF 타입을 만드는 방향 — **설계 정리 문서만** 작성 (구현 전)

- 하드코딩 메타 → 입력단에서 스키마·키:밸류·내용평가·영상적합도·키워드 전달
- 이솝 = 첫 타입 · 내일 §9 미결 확인 후 Phase 착수

---

## 2026-07-23 (v63)

**변경 파일**: admin_frontend_react (PdfGenerate·agentClient·fableGenerate), README.md, Docs/20260722_순번27이후_어드민PDF모드_입력단_계획.md

**변경 내용**: 2차 순번 3 완료 — 어드민 `/pdf/generate`에서 원문 붙여넣기→채점→화면 PDF 다운로드·미리보기

- Agent `POST /fable/generate-pdf` 연동 · 프론트 120초 · 미리보기는 클릭 후 우측만
- 다음 권장: 실키로 1건 E2E(H) 확인 후 순번 4~

---

## 2026-07-23 (v62)

**변경 파일**: app/api/fable.py, app/fable_pdf/*, app/schemas/fable.py, tests/test_fable_*.py, pyproject.toml, Dockerfile, README.md, Docs/20260722_순번27이후_어드민PDF모드_입력단_계획.md

**변경 내용**: 2차 순번 2 완료 — `POST /fable/generate-pdf`로 원문→Groq 채점→PDF 바이너리 응답

- 서버 자동 채번(`data/fable_id_seq.txt`) · tmp 즉시삭제+TTL 24h · LLM 한도 100초
- 성공: `application/pdf` + `X-Fable-Id`/`Title` · 빈 원문 400 · 실패 502
- TDD 8통과 · Docker에 `fonts-nanum` · reportlab/matplotlib/langchain-groq 의존성

---

## 2026-07-22 (v61)

**변경 파일**: admin_frontend_react (Login·App·PdfGenerate·PdfVector·adminWorkspace·테스트), README.md

**변경 내용**: 2차 순번 1 완료 — 로그인 FAQ|/PDF 2버튼 + `/pdf` 라우트·PDF 모드 사이드 메뉴

- FAQ→`/main` · PDF→`/pdf`→`/pdf/generate` · 벡터 뼈대 `/pdf/vector`
- 딥링크 시 `guest` 저장 · TDD 17통과

---

## 2026-07-22 (v60)

**변경 파일**: README.md, Docs/20260722_순번27이후_어드민PDF모드_입력단_계획.md

**변경 내용**: 1차 백엔드(순번 27)에서 끊고 PDF 프론트는 **2차 순번 1부터** · 로그인 화면 FAQ/PDF 분기 UX 확정

- 구 28~35 → 2차 1~8
- 로그인 제목·FAQ(하늘)·PDF(분홍) 2등분 버튼
- **라우트** — FAQ=`/main` 유지 · PDF=`/pdf/*` · `/faq` 신설 안 함 (주소창 `/main` 직입 OK)
- `.gitignore`에 `data/tmp/` · `data/fable_id_seq.txt` 추가
- 딥링크 디폴트 아이디 = **`guest` 저장** (표시만 fallback 아님)
- PDF 생성 LLM: Groq · 프론트 타임아웃 **120초** · 서버 **100초** · 실패 시 다시 시도
- PDF 저장: `data/tmp/fable_pdf/` · 즉시삭제+TTL 24h · 체크 시에만 `data/uploads/`
- **2차-7 배치 보류** · MVP는 **1건 생성 + 화면 PDF 다운로드** 우선
- 우화 ID는 **서버 자동 채번** (UI 입력란 없음)
- `/pdf/generate`: 완료 후 다운로드·미리보기·다시만들기 · **미리보기 클릭 시에만** 우측 PDF
- 생성 화면 uploads 체크 제거 (벡터화와 분리)
- **DB 테이블은 1건 생성 통과 후** 계획 (현재 MVP는 파일 시퀀스)

---

## 2026-07-22 (v59)

**변경 파일**: Docs/20260722_순번27이후_어드민PDF모드_입력단_계획.md, README.md

**변경 내용**: 순번 27 이후를 28~35로 세분 — 어드민 FAQ|PDF 분리·PDF 입력단·hub 딥링크 계획 확정

- 루트 `:3002`=로그인 유지, hub 카드는 `/faq`·`/pdf` index 직행
- FAQ 벡터(엑셀+QA)와 PDF 벡터는 선택 순간부터 다른 페이지
- 구 순번 25(배치+입력단) → 28~35 분해

---

## 2026-07-22 (v58)

**변경 파일**: Docs/20260722_LangGraph-Agentic-backend_순번23_compose_계획.md, docker-compose.hetzner.yml, .env.hetzner.example, tests/test_hetzner_compose.py, README.md, .gitignore

**변경 내용**: 순번 23 — Hetzner compose에 LangGraph-Agentic-backend·Qdrant 규약 추가, 레거시 regline_hub 제거

- 서비스 `langgraph_agentic`(:8010) · `qdrant`(:6333) · env `QDRANT_HOST=qdrant` · `.env.hetzner.example`
- Vercel로 옮긴 `regline_hub`(:3003) 블록 삭제
- 기동·헬스 확인은 순번 24 (CPX22 OOM 주의)

---

## 2026-07-22 (v57)

**변경 파일**: Docs/20260722_LangGraph-Agentic-backend_순번22_Dockerfile_계획.md, Dockerfile, .dockerignore, tests/test_dockerfile.py, README.md

**변경 내용**: 순번 22 — 배포용 `Dockerfile` + `.dockerignore` 완료 (app/ingest만 이미지, tests·.env 제외)

- `EXPOSE 8010` · `uvicorn app.main:app` — compose(23)에서 스택 연결 예정
- pytest `test_dockerfile` 2통과로 계약 고정

---

## 2026-07-21 (v56) — 우화 312편·입력단은 배포 후

**변경 파일**: README.md

**변경 내용**: 순번 25(우화 312편·업로드 입력단)는 **배포(22→24) 끝난 뒤** 진행. 내일은 배포만

---

## 2026-07-21 (v55) — Phase D PDF 도메인 라우터 (완료)

**변경 파일**: app/graph/domain_router.py, app/graph/runtime.py, app/tools/search_holdings.py, app/graph/groq_decision.py, app/graph/workflow.py, tests/test_domain_router.py

**변경 내용**: PDF 모드에서 **Groq 도메인 분류(이솝 vs ARKK)** 후 이솝만 규칙 라우터, ARKK는 `arkk_holdings_bge` 검색 + Groq Tool 루프

- `classify_pdf_domain` — Groq JSON + 키워드 폴백
- `run_agent_chat` — holdings 분기 시 catalog·MBTI 등 우화 규칙 스킵
- pytest `test_domain_router` 8통과, 전체 116통과
- H: 프론트 PDF 모드 — 우화·ARKK 샘플 질문 정상 확인

---

## 2026-07-21 (v54) — Phase C ARKK ingest (완료)

**변경 파일**: ingest/holdings_metadata.py, ingest/ingest_arkk.py, ingest/arkk_manifest.yaml, scripts/ingest_arkk_holdings.py, app/config.py, ingest/index_documents.py, tests/test_arkk_holdings_ingest.py, pyproject.toml, .env.example

**변경 내용**: ARKK holdings PDF를 **bge-m3·`arkk_holdings_bge`** 로 ingest — manifest·fund·as_of_date 메타 스탬프, 우화 `pdf_chunks_bge`와 분리

- TDD: `test_arkk_holdings_ingest` 7통과
- CLI: `python scripts/ingest_arkk_holdings.py` → **37청크** 적재 (H 확인)
- H: 우화·FAQ 회귀, PDF 모니터링(`content_channel=pdf`) 정상

---

## 2026-07-21 (v53) — PDF 도메인 라우터·ARKK ingest (계획)

**변경 파일**: Docs/20260721_PDF모드_도메인라우터_ARKK_ingest_계획.md, README.md

**변경 내용**: Phase C/D **예정 파일 경로**를 계획서·README §2·§4-1에 명시 (ingest_arkk, arkk_manifest, ingest_arkk_holdings 등) — 착수

---

## 2026-07-21 (v52) — 목록 질문 공백 정규화

**변경 파일**: Docs/20260721_목록질문_공백정규화_계획.md, app/metrics/catalog.py, tests/test_human_test_fixes.py

**변경 내용**: 「전체 목록」「목록」도 **등록 우화 제목 전량**을 보여 줌. catalog 매칭만 공백 제거, 단독 `목록`은 exact 매칭으로 「키워드 목록」오탐 방지

- 검증: `test_human_test_fixes` 13통과

---

## 2026-07-20 (v51) — PDF만 유사도0 숨김·메타 표기

**변경 파일**: frontend_react/src/App.jsx

**변경 내용**: PDF(`agent_chat`)에서 벡터 검색을 안 탄 답은 **유사도 0.000 대신「출처: 메타/문서」**. FAQ 유사도 표시는 분기 밖으로 두어 변경 없음

---

## 2026-07-20 (v50) — Agent 응답에 Qdrant 유사도 score

**변경 파일**: app/schemas/agent.py, app/graph/nodes.py, app/api/agent.py, frontend_react/src/App.jsx, tests/test_agent_api.py

**변경 내용**: PDF Agent 검색 시 Qdrant **유사도 score**를 citations에 담고, 프론트 PDF 채널이 `0.000` 고정 대신 그 점수를 표시 (키워드 가산 판단용 기반)

- 검증: `test_similarity_score_propagation` 등 단위 14통과 + 로컬 `/agent/chat` 스모크(Agent 경로 similarity≈0.63)

---

## 2026-07-20 (v49) — 짧은 애매 질문 시 제목 후보 목록

**변경 파일**: app/metrics/vague.py, tests/test_vague_question.py

**변경 내용**: 「박쥐」처럼 짧은 애매 질문에 되묻기 + **입력 글자가 들어간 우화 제목 목록**(번호·줄바꿈)을 함께 보여 줌

---

## 2026-07-20 (v48) — MBTI 안내 = mbti+변경의도 정규식

**변경 파일**: app/metrics/mbti_commands.py, tests/test_mbti_commands.py

**변경 내용**: MBTI 설정 안내를 부분문자열 목록이 아니라 **`mbti`/`유형` + 변경·설정 의도 동사 정규식**으로 잡음. 「유형별 해석」은 제외

---

## 2026-07-20 (v47) — MBTI 재해석 = 한마디+MBTI+70자만

**변경 파일**: app/metrics/mbti_reinterpret.py, tests/test_mbti_tone.py

**변경 내용**: 유형별 해석에서 **톤 맵(유머/시적/진지) 제거**. LLM 입력은 문서 한마디 결론+MBTI, 출력 제약은 두 문장·70자 — 뉘앙스는 모델이 유형으로 판단

---

## 2026-07-20 (v46) — MBTI 재해석 톤 = 유형별 고정

**변경 파일**: app/metrics/mbti_reinterpret.py, tests/test_mbti_tone.py

**변경 내용**: 유형별 해석 톤을 **랜덤이 아니라 MBTI 고정 맵**으로 변경 — v47에서 톤 레이어 자체를 제거

---

## 2026-07-20 (v45) — MBTI 재해석 톤 랜덤 강제

**변경 파일**: app/metrics/mbti_reinterpret.py, tests/test_mbti_tone.py

**변경 내용**: 사람테스트 16번 — 유형별 해석 톤을 프롬프트 희망사항이 아니라 **코드에서 진지/유머/시적 중 하나를 골라** LLM에 강제 (v46에서 고정 맵으로 대체)

---

## 2026-07-20 (v44) — 한마디+MBTI면 유형별 해석

**변경 파일**: app/metrics/verbatim.py, tests/test_human_test_fixes.py, Docs/20260720_PDF_질문_트리거_가이드.md

**변경 내용**: **MBTI가 설정된 뒤「한마디 결론」**은 문서 복붙이 아니라 **유형별 LLM 재해석**(두 문장·70자). MBTI 없을 때만 문서 한마디 그대로

---

## 2026-07-20 (v43) — 사람테스트 이슈 수정 (완료)

**변경 파일**: Docs/20260720_LangGraph_사람테스트_이슈수정_계획.md, Docs/20260720_PDF_질문_트리거_가이드.md, app/metrics/*, app/graph/*, app/tools/lookup_fable_metadata.py, tests/test_human_test_fixes.py

**변경 내용**: 사람테스트 P0·P1 반영 — **한마디 결론은 문서 그대로**, 재해석만 LLM(두 문장·70자), 목록·재미 Top 규칙, MBTI 안내·제목 부분일치·「그대로 읽어」, Agent 무근거 답 차단

- 가이드: `Docs/20260720_PDF_질문_트리거_가이드.md`

---

## 2026-07-20 (v42) — Agent 전체 흐름 · 검색 세부 흐름 문서

**변경 파일**: Docs/20260720_LangGraph_Agent_전체흐름_검색세부흐름.md

**변경 내용**: 사용자 질문 → **규칙 라우터(metrics)** → **LangGraph Agent 루프(검색 세부)**까지 흐름·코드 위치·LLM 여부를 한 문서로 정리 (티스토리·온보딩용)

---

## 2026-07-20 (v41) — 티스토리 LangGraph 4편 HTML 뼈대

**변경 파일**: Docs/tistory/09_*.html, Docs/20260720_티스토리_LangGraph_Agentic_4편_계획.md

**변경 내용**: 티스토리용 LangGraph Agentic **4편 HTML**을 미리 둠. 본문·캡션만 있고 **이미지 자리는 회색 슬롯** — 발행 전 사람이 채움

---

## 2026-07-20 (v40) — 이야기입력→PDF생성 계획·티스토리 4편 합의

**변경 파일**: Docs/20260720_사용자이야기입력_PDF생성_어드민_계획.md, Docs/20260720_티스토리_LangGraph_Agentic_4편_계획.md

**변경 내용**: 어드민 **이야기 입력→PDF 생성** 계획(화면 텍스트 그림) + 티스토리 LangGraph 시리즈 **4편** 목차 확정

- 1 왜 Agentic RAG · 2 문서기반 답변 · 3 bge-m3/Qdrant · 4 이야기→PDF

---

## 2026-07-20 (v39) — FAQ Chroma bge-m3 교체 포기

**변경 파일**: README.md

**변경 내용**: FAQ(Chroma)를 bge-m3로 바꾸는 작업은 **하지 않기로 함** — MiniLM·기존 품질보정 코드 유지, PDF Agent만 bge-m3

- 이유: 하드코딩·threshold/키워드합산 재검증 부담이 커서 검색만 되고 품질 레이어를 다시 훑게 될 위험이 큼

---

## 2026-07-20 (v38) — 제목만 입력 시 카드 전체

**변경 파일**: app/metrics/title_card.py, app/graph/runtime.py, tests/test_title_full_card.py

**변경 내용**: 채팅에 **우화 제목만** 치면 LLM 없이 **내용+한마디 결론+내용평가+키워드**를 한꺼번에 보여 줌

- `내용은`/`줄거리`는 본문만, 제목만은 카드 전체

---

## 2026-07-20 (v37) — 내용·줄거리 = 원문 그대로

**변경 파일**: app/metrics/verbatim.py, app/metrics/vague.py, tests/test_verbatim_body.py, tests/test_ambiguous_content.py

**변경 내용**: 사용자가 많이 치는 **「내용」「줄거리」**도 「원문」과 같이 **본문 그대로** 보여 줌 (LLM 요약 금지)

- `내용평가`는 기존 metadata 경로 유지

---

## 2026-07-20 (v36) — 「내용은」애매 되묻기 완료

**변경 파일**: app/metrics/vague.py, tests/test_ambiguous_content.py

**변경 내용**: (v37에서 내용→원문으로 변경) 애매 단독어 되묻기 원칙은 유지

---

## 2026-07-20 (v35) — 순번 21 FakeEmbed → bge-m3 완료

**변경 파일**: Docs/…계획.md, ingest/bge_m3.py, ingest/embedder_factory.py, ingest/index_documents.py, app/graph/runtime.py, app/config.py, pyproject.toml, scripts/reingest_three_fables.py, README.md, tests/test_bge_m3_embedder.py

**변경 내용**: PDF 검색·인제스트를 **bge-m3(1024)** 로 바꿔 제목·「내용은」이 맞는 우화 PDF를 찾게 함

- 설정 `EMBEDDING_BACKEND=bge-m3`, 컬렉션 **`pdf_chunks_bge`** (옛 32차원 `pdf_chunks`와 분리)
- 테스트 3편 재적재 · 검색 top-1이 해당 파일로 맞음 (유사도 UI·FAQ 교체는 품질 확인 후)

---

## 2026-07-20 (v34) — 「평가는」내용평가 인식 완료

**변경 파일**: app/metrics/detect.py, app/graph/runtime.py, tests/test_metric_route.py

**변경 내용**: 채팅 `평가는`·`평가`를 **내용평가**로 인식해 단기 메모리 우화의 4지표가 나오게 함

- `최종평가`는 먼저 매칭해 내용평가와 구분
- 지표 라우트를 짧은 애매 되묻기보다 **앞에** 두어 `평가는`가 「어떤 우화…」로 새지 않게 함

---

## 2026-07-20 (v33) — 한마디 결론 라벨·트리거·단독 되묻기 완료

**변경 파일**: Docs/…계획.md, ingest/fable_parse.py, app/metrics/vague.py, app/metrics/verbatim.py, app/graph/runtime.py, scripts/reingest_three_fables.py, tests/*

**변경 내용**: PDF **한마디 결론**을 modern으로 파싱하고, 채팅 트리거·단독 애매어 되묻기·테스트 3편 재적재까지 맞춤

- 파서: `한마디 결론` (+ 하위 호환 `오늘날로 치면`) → `content_type=modern`
- 채팅: `한마디`/`재해석` 등 → MBTI 없으면 카드 본문, 있으면 유형별 LLM / 단독 `해석`·`결론`·`mbti`는 되묻기
- `01`·`02`·`06` 3편 삭제 후 재인제스트 (`scripts/reingest_three_fables.py`)

---

## 2026-07-20 (v32) — PDF/FAQ 안내·MBTI 메모리·유형별 해석 완료

**변경 파일**: Docs/…계획.md, app/metrics/memory.py, app/metrics/mbti_*.py, app/metrics/verbatim.py, app/graph/runtime.py, app/schemas/agent.py, frontend_react/src/App.jsx, tests/test_mbti_*.py

**변경 내용**: PDF/FAQ 채널 전환 안내글, `MBTI : xxx` 단기 메모리, MBTI 있을 때 LLM **유형별 해석**, 질문 키워드(`재해석`·`MBTI 유형별 해석`)까지 통과

- FAQ↔PDF 전환 시 안내문 교체 · MBTI 있으면「현재 MBTI는 ○○○」·수정 안내는 `mbti 변경`/`설정변경` 칠 때만
- MBTI 없으면 `오늘날로 치면(modern)` 카드 본문 그대로, 있으면 유형별 LLM 해석
- `/agent/chat` 응답에 `mbti`를 실어 UI가 PDF 안내 상태를 맞춤

---

## 2026-07-20 (v31) — MBTI 유형별 해석 용어·동작 합의 (문서)

**변경 파일**: Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md

**변경 내용**: 사용자 표기를 **「MBTI 유형별 해석」**으로 두고, MBTI 미설정 시에는 기존 `오늘날로 치면(modern)` 본문을 그대로 보여 주기로 합의 기록

- PDF 안내글: MBTI 유무·FAQ→PDF 전환에 따라 안내 변경 · 수정 안내는 `mbti 변경`/`설정변경` 칠 때만
- **새로고침 안내 문구는 무시(미표기)**
- MBTI LLM 유형별 해석·UI 구현은 대기 · 코딩 없음 (문서만)

---

## 2026-07-20 (v30) — 원문/오늘날로 치면 그대로 응답 완료

**변경 파일**: Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md, app/metrics/verbatim.py, app/tools/lookup_fable_metadata.py, app/graph/runtime.py, tests/test_verbatim_body.py

**변경 내용**: 「원문은」「오늘날로 치면」은 Groq 요약 없이 **본문 청크를 그대로** 반환 (교훈 문장 포함)

- 「줄거리」는 기존처럼 요약 경로 유지
- 제목 없·메모리 없으면 되묻기

---

## 2026-07-20 (v29) — 짧은 애매 질문 되묻기 완료

**변경 파일**: Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md, app/metrics/vague.py, app/graph/runtime.py, tests/test_vague_question.py

**변경 내용**: 「늑대」처럼 제목·의도 없이 짧은 질문은 검색·Groq 요약 없이 **되묻기** (줄거리 단정·근거 인용 금지)

- 「너 누구야」·제목 포함·지표 질문은 기존 경로 유지
- 계획 §3-D C1 반영

---

## 2026-07-20 (v28) — 내용평가·키워드 metadata 라우팅 완료

**변경 파일**: Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md, app/metrics/*, app/tools/lookup_fable_metadata.py, app/graph/runtime.py, app/api/agent.py, app/schemas/agent.py, app/qdrant_factory.py, frontend_react/src/App.jsx, tests/test_metric_route.py, tests/test_qdrant_client.py, README.md

**변경 내용**: 지표·키워드 질문은 벡터 검색 대신 **metadata 조회**로 답함 — 제목·`session_id` 단기 메모리·되묻기

- 예: 내용평가 4지표, 키워드 목록, 「재미도는 몇이야」→ 2/5 또는 되묻기
- UI PDF 호출에 `session_id` 전달. 유사도 표시는 순번 21 이후
- **수정:** 로컬 Qdrant PATH 이중 open으로 UI 502 나던 문제 → `get_shared_qdrant_client`로 프로세스당 1개만 사용

---

## 2026-07-20 (v27) — 순번 21 이후 유사도 분기 README 기술

**변경 파일**: README.md, Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md

**변경 내용**: 실임베딩(순번 21) **결과 확인 후** 유사도만 쓸지, FAQ식 **유사도+키워드매칭 합산(21b)** 할지 README에 분기해 둠

- 지금은 21 이전 — 유사도 표시·합산은 21 이후에 결정
- metadata 질문(내용평가 등)은 유사도 해당 없음 유지

---

## 2026-07-20 (v26) — 내용평가·키워드 라우팅 계획 (기대 답변 합의)

**변경 파일**: Docs/20260720_LangGraph-Agentic-backend_내용평가_키워드_라우팅_계획.md, Docs/20260720_내용평가질문라우팅_작업지시서.md

**변경 내용**: 내용평가·키워드를 **같은 metadata 경로**로 두는 계획과 **질문별 기대 답변**을 문서화함 (구현 전 합의용)

- 샘플(늑대와 어린양) 4지표·키워드 기대값 명시
- **312편 벡터화만으로는 「내용평가는」 대상이 안 정해짐** → 단기 메모리(직전 우화)로 특정 후 metadata 조회 (계획 §1-1)
- **최우선:** 질문 형태와 무관하게 맞는 답 / 모름 / 되묻기만 허용 — 엉뚱한 답 금지 (계획 §0-1)
- 「재미도는 몇이야」 기대값 합의: 맥락 있으면 2/5, 없으면 되묻기 (계획 A9·A10)
- 구현은 §3 나머지 동의 후에만 착수

---

## 2026-07-19 (v25) — UI CORS 고정 완료

**변경 파일**: Docs/20260719_LangGraph-Agentic-backend_CORS고정_계획.md, app/main.py, tests/test_cors.py

**변경 내용**: 챗봇 UI → PDF Agent(:8010)가 브라우저에서 응답을 읽을 수 있게 CORS를 고정함 (`*` + credentials 충돌 제거)

- `allow_credentials=False` (쿠키 미사용). FAQ(:9000)는 변경 없음
- `tests/test_cors.py`로 Origin=localhost:3001 계약 검증

---

## 2026-07-19 (v24) — 작업순서 번호 재정렬 (구 9 → 21)

**변경 파일**: README.md

**변경 내용**: 실행 순서와 번호를 맞춤 — 실임베딩을 **21**, 배포를 **22~24**, 배치를 **25**로 정리

- 구 순번 **9**는 표에 `[이동]` 결번으로 남기고, 본문은 21을 가리킴
- **다음** = 21 `bge-m3` → FAQ Chroma 교체 → 22 Dockerfile

---

## 2026-07-19 (v23) — 작업순서 순번 24 배치 인제스트 추가

**변경 파일**: README.md

**변경 내용**: 작업순서도에 **순번 24** — uploads PDF 일괄 인제스트 + 성공/실패 리포트(우화 312편 등)를 체크 항목으로 추가

- 구현은 나중 · 진행 현황은 README §1에서 체크

---

## 2026-07-19 (v22) — 우화 메타데이터 청킹 완료

**변경 파일**: Docs/20260719_LangGraph-Agentic-backend_우화메타데이터청킹_계획.md, ingest/fable_parse.py, ingest/chunk.py, ingest/load_pdf.py, ingest/index_documents.py, tests/test_fable_metadata.py, README.md

**변경 내용**: 이솝 우화 분석 카드는 **점수·키워드를 metadata**로 두고, **원문/오늘날로 치면만** 본문 청크로 나눠 검색·필터에 쓰게 함

- `load_pdf`가 줄바꿈을 유지해야 라벨 파싱이 됨 (공백 한 줄 뭉개기 제거)
- 일반 PDF는 기존 청킹 유지 · Qdrant payload에 `fun`·`keywords` 등 전달

---

## 2026-07-18 (v21) — 순번 21 Dockerfile 착수

**변경 파일**: Docs/20260718_LangGraph-Agentic-backend_Dockerfile_계획.md

**변경 내용**: Phase 착수 — 배포용 `Dockerfile`/`.dockerignore` (`app`·`ingest`만, `tests/` 제외, 포트 8010)

- 순번 22 compose·23 배포 기동은 다음 Phase
- MBTI 고전 컨셉은 보류, Agentic 하단 작업 우선

---

## 2026-07-18 (v20) — 고전 원문 + MBTI 현대 재해석 컨셉

**변경 파일**: Docs/20260718_고전원문_MBTI현대재해석_컨셉.md, Docs/20260718_고전명언_냉소현대변환_컨셉.md, README.md

**변경 내용**: 별도 제품 후보를 **질문→검색 1회→고전체 고정 + MBTI 현대체** 구조로 문서를 새로 확정

- README에는 문서명만 링크 (`Docs/20260718_고전원문_MBTI현대재해석_컨셉.md`)
- 이전 명언 냉소 변환 메모는 초안 보관·후속 문서로 안내

---

## 2026-07-18 (v19) — 청킹 품질 개선 완료

**변경 파일**: Docs/20260718_LangGraph-Agentic-backend_청킹품질_계획.md, ingest/chunk.py, ingest/index_documents.py, tests/test_chunk_quality.py, README.md

**변경 내용**: PDF 청킹을 글자 mid-cut에서 **문단·줄·문장부호 우선(기본 300/60)** 으로 바꿔 검색용 청크 경계를 개선

- Separator 순서: `\n\n` → `\n` → `.?!。` → 공백 → hard cut (어미 휴리스틱·표 보존 없음)
- `tests/test_chunk_quality.py` + 전체 pytest 통과; 적용 후 `pdf_chunks` **재인제스트 필수** (README §8)

---

## 2026-07-18 (v18) — API 포트 8005 → 8010

**변경 파일**: app/config.py, .env.example, README.md, frontend_react/.env.development, frontend_react/src/App.jsx

**변경 내용**: LangGraph-Agentic API 기본 포트를 **8010**으로 변경 (Tomcat 등과 연상되는 8005 회피)

- FAQ `:9000` · Chroma `:8000` 과 충돌 없음
- 프론트 `REACT_APP_AGENT_API_URL` 기본값도 `http://localhost:8010`으로 맞춤

---

## 2026-07-18 (v17) — 파이프라인 다이어그램 초안

**변경 파일**: Docs/20260718_LangGraph-Agentic-backend_파이프라인_다이어그램.md, Docs/20260718_rag_and_agent_merged_flow.html, Docs/rag_and_agent_merged_flow_v2.svg

**변경 내용**: 파이프라인 다이어그램 문서 + **v2 SVG**를 HTML로 표시

- `Docs/20260718_rag_and_agent_merged_flow.html` — `rag_and_agent_merged_flow_v2.svg` 그대로 삽입(표시 50%)
- 설명 문단은 다이어그램 확정 후 작성 예정

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
