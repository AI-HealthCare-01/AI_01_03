# 👤 김빛나 (RAG·LLM) — feature/llm-guide (현재 브랜치: binna/llm)

## ✅ DoD (개발 완료 기준)

* [x] 지식문서 생성
* [x] FAISS 인덱싱 완료
* [x] `/api/chat` 동작 (FAISS 실연동 완료)
* [x] 임계값 기반 안전응답 구현
* [x] 출처 + 면책 고정 포함

---

## 📅 03/02(월)

### 오전
* [x] System Prompt 초안 작성
  - `app/prompts/system_prompt.py`
  - 역할 정의, 5개 핵심 규칙(컨텍스트 기반, 면책, 출력 형식, 스타일, 금지사항)
  - `DISCLAIMER`, `SAFE_FALLBACK_ANSWER` 상수 정의
  - `build_system_prompt()`, `build_chat_prompt(context, question)` 함수

### 오후
* [x] 컨텍스트 외 답변 금지 규칙 고정
  - `app/prompts/system_prompt.py` — 프롬프트 내 "Context에 없는 내용은 절대 답변하지 마세요" 규칙
  - `app/services/llm_guide.py` — `contains_out_of_scope_marker()` 가드레일 메서드

### 야간
* [x] 출력 포맷 템플릿 정의
  - `app/dtos/chat.py` — `ChatRequest`, `ChatResponse`, `ChatErrorResponse`, `AnswerSections`, `Citation`
  - 4섹션 구조: summary, dosage, precautions, tips
  - Sprint01 통합 계약서 섹션 4 스펙 준수

---

## 📅 03/03(화)

### 오전
* [x] 식약처 API 파싱 스크립트 작성
  - `scripts/fetch_drug_info.py`
  - e약은요 API (`getDrbEasyDrugList`) 연동 — 일반의약품 상세 정보 수집
  - Excel 양쪽 시트(1000+정보, 4000+정보) 읽기 지원 — 총 4,998건
  - 다단계 검색 전략 (괄호 제거, 숫자/단위 제거, 핵심 약명 추출)
  - 체크포인트 저장/재개(`--resume`) 지원
  - API 필드 매핑: efcyQesitm→efficacy, useMethodQesitm→dosage, atpnQesitm→precautions 등

### 오후
* [x] 지식 JSON 생성 → `data/knowledge_base.json`
  - 전체 4,998건 수집 완료 (API 데이터 756건, 15.1%)
  - FAISS 인덱스 재빌드 완료: 758 벡터 (유효 청크)
  - 허가정보 API 승인됨 — 추후 전문의약품 보강 가능

### 야간
* [x] 데이터 라이선스 리스크 기록

### 추가 완료 항목 (03/03)
* [x] .env 환경변수 구조 설계 및 API 키 등록
  - `.env` — OCR, 식약처(e약은요 + 허가정보), OpenAI, GLM-5 키 관리
  - `app/core/config.py` — `Config` 클래스에 전체 설정 반영
* [x] GLM-5 (Zhipu AI) API 연동 완료
  - Kilo AI Gateway 경유: `https://api.kilo.ai/api/gateway`
  - 모델 ID: `z-ai/glm-5` (reasoning 모델, content + reasoning 필드 반환)
  - `app/services/llm_guide.py` — `AsyncOpenAI` 클라이언트 2개 (GLM-5 + GPT-4o-mini)
  - `call_glm()`, `call_openai()`, `generate_answer()` 메서드 구현
* [x] `/api/chat` 엔드포인트 LLM 실연동
  - `app/apis/v1/chat_routers.py` — mock 응답 → GLM-5 실호출로 교체
  - 파이프라인: FAISS검색(mock) → 임계값검증 → GLM-5 답변생성 → 안전응답감지 → 응답조립
* [x] LLM 이중 구조 확정
  - 프론트 (채팅 응답): GPT-4o-mini (`OPENAI_*` 설정)
  - 백엔드 (RAG reasoning/agent): GLM-5 (`GLM_*` 설정)

---

## 📅 03/04(수)

### 오전
* [x] Chunk 규칙 확정
  - 약품 1건 = 문서 1개 (전체 텍스트 필드 결합)
  - 헤더: `[약품명] 이름 (카테고리) — 제조사`
  - 본문 섹션: 효능/효과, 용법/용량, 주의사항, 경고, 상호작용, 부작용, 보관법
  - 빈 필드 제외하여 노이즈 최소화

### 오후
* [x] 임베딩 → FAISS 인덱스 생성
  - 모델: `paraphrase-multilingual-MiniLM-L12-v2` (384차원, 한국어 지원)
  - 인덱스: `IndexFlatIP` (정규화 벡터 → Inner Product = Cosine Similarity)
  - `scripts/build_faiss_index.py` — 빌드 스크립트
  - `app/services/rag_search.py` — 런타임 검색 서비스 (싱글톤)
  - `chat_routers.py` — Mock 제거, 실제 FAISS 검색 연동 완료

### 야간
* [x] 검색 점수 기반 임계값 설정
  - cosine similarity 기반 (높을수록 유사, 0~1 범위)
  - 임계값: 0.45 (config.py `RAG_CONFIDENCE_THRESHOLD`)
  - "타이레놀 복용법" → 0.76, "두통약" → 0.69, 경계 사례 → 0.44

---

## 📅 03/05(목)

### 오전
* [x] LLM 호출 래퍼 구현 → (03/03에 앞당겨 완료)

### 오후
* [x] `/api/chat` 구현 → (03/03에 앞당겨 완료)

### 야간
* [x] 안전응답 + Draft PR 제출
  - 안전응답 2단계 검증: RAG 임계값(Step 2) + LLM 안전문구 감지(Step 4)
  - RAG 검색 없음/임계값 미달 → `422 LOW_RAG_CONFIDENCE`
  - LLM 스스로 범위 밖 판단 → `422 LOW_RAG_CONFIDENCE`

---

## 📅 03/06(금)

### 오전
* [ ] UI PR 리뷰

### 오후
* [x] 문장 단위 분할(TTS 세그먼트)
  - `llm_guide.py:split_tts_segments()` 개선
  - 3단계 분할: 줄바꿈 → 문장부호(. ! ? 。) → 쉼표(200자 초과 시)
  - 불릿 마커(-, *, •) 자동 제거

### 야간
* [x] 응답 시간 측정(5초 목표)
  - `scripts/benchmark_chat.py` 벤치마크 스크립트 작성
  - RAG 검색: avg 23ms (첫 쿼리 435ms 모델 로딩 포함)
  - 5초 이내 응답 충분히 달성 가능 (RAG 20ms + LLM ~2-3초)

---

## 📅 03/07(토)

### 오전
* [ ] develop 병합

### 오후
* [ ] E2E 질문 → 답변 → TTS 확인

### 야간
* [x] 출처 표기 규칙 확정
  - 응답 내 `citations` 배열: `[{source, title}]`
  - `source`: "식약처 의약품안전나라" (고정)
  - `title`: 검색된 약품명 (FAISS Top-K 결과)
  - `disclaimer`: 의료 면책 조항 항상 포함 (DISCLAIMER 상수)
  - 공공누리 제4유형 출처 표기 준수

---

## 📅 03/08(일)

### 오전
* [x] 평가 질문 20개 구성
  - `scripts/benchmark_chat.py` 내 `EVAL_QUESTIONS` (20개)
  - 카테고리: specific(5), symptom(5), ambiguous(2), edge(3), out_of_scope(5)

### 오후
* [x] 오답/환각 패턴 정리
  - RAG-only 벤치마크 결과: 14/20 정확도 (70%)
  - **패턴 1: 미등록 약품** — "판콜에이" score=0.43 (인덱스에 없음 → 안전응답 정상)
  - **패턴 2: 모호한 질문** — "이 약 먹어도 돼?" score=0.71 (의도 불명확 → RAG 오매칭)
  - **패턴 3: 범위 밖 고점수** — "피자 추천", "파이썬 코드" score=0.54~0.64 (의미적 유사도 과대)
  - **대응**: Step 4 LLM 가드레일이 2차 필터링 (Context 외 답변 금지 규칙)
  - 결과 저장: `data/benchmark_results.json`

### 야간
* [x] OpenAI 사용량 모니터링 포인트 정리
  - GLM-5 (Kilo AI): 요청당 max_tokens=2048, temperature=0.3
  - GPT-4o-mini: 요청당 max_tokens=1024, temperature=0.3
  - 모니터링 포인트: `llm_guide.py:call_glm()`, `call_openai()`
  - 비용 추적: Kilo AI 대시보드 + OpenAI Usage 페이지

---

## ⚠ 리스크

### 1. 데이터 라이선스 — ✅ 확인 완료

| 항목 | 내용 |
|------|------|
| **API** | 식약처 e약은요 (`15075057`), 의약품 허가정보 (`15095675`) |
| **라이선스** | 공공누리 제4유형 (출처표시-상업적이용금지-변경금지) |
| **학술/교육 사용** | ✅ 허용 (비영리 프로젝트 해당) |
| **출처 표기** | 필수 — "식품의약품안전처 공공데이터 이용, 공공누리 제4유형" |
| **상업적 이용** | ❌ 불가 — 상용화 시 별도 라이선스 필요 |
| **2차 가공/변경** | ❌ 불가 — 원본 그대로 사용, 데이터 수정 배포 금지 |
| **재배포** | ❌ 불가 — JSON 원본을 외부 공개 불가 |

**의료 AI 특수 리스크:**
- LLM 학습 데이터로의 직접 파인튜닝은 "변경"에 해당할 수 있음 → RAG(검색 참조) 방식은 원본 참조이므로 적합
- 진단/치료 추천 시 의료기기 인허가(MFDS) 별도 필요 — 본 프로젝트는 일반 건강정보 안내 범위
- 면책 조항(DISCLAIMER) 고정 출력으로 법적 리스크 최소화 중

**준수 사항:**
```
본 서비스는 식품의약품안전처의 공공데이터(e약은요, 의약품 허가정보)를 이용합니다.
공공누리 제4유형(출처표시-상업적이용금지-변경금지)에 따라 이용합니다.
```

### 2. 환각 리스크 — ✅ 평가 완료
* [x] 평가 질문 20개 벤치마크 실행 → RAG 정확도 70% (14/20)
* 주요 패턴: 미등록 약품 miss, 모호한 질문 오매칭, 범위 밖 고점수
* LLM Step 4 가드레일로 2차 필터링 대응

### 3. 응답 지연 — ✅ 측정 완료
* [x] RAG 검색 avg 23ms, 5초 목표 충분히 달성

---

## 📁 주요 파일 경로 정리

| 파일 | 역할 |
|------|------|
| `app/prompts/system_prompt.py` | System Prompt 템플릿, DISCLAIMER, SAFE_FALLBACK_ANSWER |
| `app/dtos/chat.py` | 요청/응답 DTO (ChatRequest, ChatResponse, ChatErrorResponse) |
| `app/services/llm_guide.py` | RAG + LLM 서비스 (GLM-5 + GPT-4o-mini), TTS 세그먼트 |
| `app/services/rag_search.py` | FAISS 검색 서비스 (싱글톤, 인덱스 로드/쿼리) |
| `app/apis/v1/chat_routers.py` | POST `/api/v1/chat` 엔드포인트 (FAISS 실연동) |
| `app/apis/v1/__init__.py` | v1 라우터 등록 (chat_router 포함) |
| `app/core/config.py` | 전체 환경 설정 (DB, JWT, 식약처, OpenAI, GLM-5) |
| `.env` | API 키 관리 (OCR, 식약처, OpenAI, GLM-5) |
| `scripts/fetch_drug_info.py` | 식약처 e약은요 API 파싱 스크립트 |
| `scripts/build_faiss_index.py` | FAISS 인덱스 빌드 스크립트 |
| `scripts/benchmark_chat.py` | 벤치마크 + 평가 질문 20개 스크립트 |
| `data/knowledge_base.json` | 의약품 지식 JSON (4,998건) |
| `data/faiss_index.bin` | FAISS 인덱스 (758 벡터, 384차원) |
| `data/faiss_meta.json` | FAISS 메타데이터 + 청크 텍스트 |
| `data/benchmark_results.json` | 벤치마크 결과 |
| `app/tests/chat_apis/test_chat_api.py` | Chat API 테스트 |
