---
tags: [타임라인, 2단계, 개발, Sprint1, 요약]
기간: 1주
상태: 진행중 (3/4~3/5 핵심 개발 완료)
시작일: 2026-02-27
종료일: 2026-03-05
---

# 2️⃣ 2단계 — 개발 Sprint 1 (백엔드, 1주)

> 상위 문서: [[전체 타임라인]] | [[🏠 요약 - 프로젝트 홈]]

**기간**: 2026-02-27 (목) ~ 2026-03-05 (수)
**목표**: 백엔드 API 및 AI 서비스 개발 완료

---

## 체크리스트

### 🔧 인프라 구축
- [ ] AWS 계정 및 권한 설정
- [ ] S3 버킷 생성 (이미지 저장용)
- [ ] RDS PostgreSQL 인스턴스 생성
- [ ] EC2 인스턴스 또는 Lambda 함수 설정
- [ ] API Gateway 설정
- [ ] 환경 변수 및 시크릿 관리 (AWS Secrets Manager)

### 🤖 AI 서비스 개발
- [ ] OpenAI GPT-4o Vision API 연동 (알약 식별)
- [ ] Naver CLOVA OCR API 연동 (처방전 스캔)
- [ ] RAG 파이프라인 구축
  - [ ] 임베딩 모델 선정 및 테스트
  - [ ] Vector DB 구축 (Pinecone 또는 FAISS)
  - [ ] 약학정보원, 식약처 데이터 수집 및 임베딩
- [ ] LLM 가이드 생성 서비스
  - [ ] System Prompt 엔지니어링
  - [ ] RAG 컨텍스트 검색 로직
  - [ ] 응답 생성 및 후처리

### 🖥️ 백엔드 API 개발
- [ ] FastAPI 프로젝트 초기 설정
- [ ] 사용자 인증/인가 (JWT)
- [ ] 사용자 서비스
  - [ ] 회원가입/로그인 API
  - [ ] 프로필 조회/수정 API
- [ ] 비전/OCR 서비스
  - [ ] 알약 이미지 업로드 및 분석 API
  - [ ] 처방전 이미지 업로드 및 OCR API
- [ ] LLM 가이드 서비스
  - [ ] 복약 가이드 생성 API
  - [ ] AI 챗봇 대화 API
- [ ] 복약 이력 서비스
  - [ ] 이력 저장/조회 API
  - [ ] 대시보드 데이터 API

### 🧪 테스트
- [ ] 각 API 엔드포인트 단위 테스트
- [ ] Vision AI 정확도 테스트
- [ ] OCR 정확도 테스트
- [ ] LLM 응답 품질 테스트
- [ ] API 성능 테스트 (5초 이내 목표)

---

## 일정 계획

| 날짜 | 주요 작업 |
|------|-----------|
| **2/27 (목)** | 인프라 구축, FastAPI 프로젝트 초기 설정 |
| **2/28 (금)** | 사용자 인증/인가, Vision AI 연동 |
| **3/1-2 (주말)** | OCR 연동, RAG 파이프라인 구축 |
| **3/3 (월)** | LLM 가이드 서비스 개발 |
| **3/4 (화)** | 복약 이력 API, 챗봇 API 개발 ✅ |
| **3/5 (수)** | 통합 테스트 및 버그 수정 ✅ (3/4 선반영) |

---

## 2026-03-04 진행 결과

- 통합 API 구현 확인: `/api/vision/identify`, `/api/ocr/parse`, `/api/chat`
- 처방전 저장 및 스케줄 생성 로직 반영 (`PrescriptionFlowService`)
- 계약 테스트 통과: `app/tests/integration_apis/test_integration_contract_apis.py` (10 passed)
- 전체 테스트 통과: `app/tests` (24 passed)

---

## 산출물

| 산출물 | 상태 |
|--------|------|
| AWS 인프라 구성도 | ⬜ |
| API 명세서 업데이트 | ⬜ |
| 백엔드 소스 코드 | ⬜ |
| 단위 테스트 코드 | ⬜ |
| API 테스트 결과 보고서 | ⬜ |

---

## 주요 기술 스택

- **언어**: Python 3.13
- **프레임워크**: FastAPI
- **DB**: PostgreSQL (RDS)
- **ORM**: Tortoise ORM
- **캐시**: Redis
- **AI**: OpenAI GPT-4o-mini (개발용)
- **OCR**: Naver CLOVA OCR
- **Vector DB**: Pinecone / FAISS
- **클라우드**: AWS (S3, EC2/Lambda, RDS)

---

## 리스크 및 대응

> [!warning]
> - **OpenAI API 비용**: 개발 중 GPT-4o-mini 사용으로 비용 절감
> - **RAG 구축 시간**: Vector DB는 FAISS로 먼저 구축 후 Pinecone 이관 가능
> - **성능 목표 (5초)**: API 응답 시간 모니터링 필수, 초과 시 병렬 처리 적용

---

## 다음 단계
→ [[3단계 - 개발 Sprint 2 (웹뷰)]]
