좋습니다. **앱인토스 출시 체크리스트까지 포함한 Sprint 02 최종 정리본**을 깔끔하게 정리했습니다.
(Obsidian/Notion에 **그대로 복붙 가능**)

---

```markdown
---
tags: [스프린트, 요약]
스프린트: Sprint 02
시작일: 2026-03-09
종료일: 2026-03-13
상태: 진행중
주요업무: MVP 기능 완성 및 서비스 배포
---

# 🏃 Sprint 02 - MVP 완성 및 서비스 배포

> 상위 문서: [[전체 타임라인]] | [[🏠 요약 - 프로젝트 홈]]

---

# 스프린트 목표

> **핵심 목표**

- Lovable 기반 프론트엔드 구축
- API 명세 기반 프론트–백엔드 연결
- 알약 인식 → 복약지도 기능 동작
- 복약 알림 기능 구현
- 웹 서비스 배포
- 앱인토스 미니앱 출시

---

# 서비스 구조

본 프로젝트는 **두 가지 환경으로 배포한다.**

## 1️⃣ 웹 서비스

배포 플랫폼  
- **Vercel**

로그인 방식  
- Google OAuth  
- Kakao OAuth  

목적  
- 일반 사용자 대상 웹 서비스 제공

---

## 2️⃣ 앱인토스 미니앱

플랫폼  
- **Toss App-in-Toss**

로그인 방식  
- **Toss Login**

목적  
- 토스 앱 사용자 대상 미니앱 서비스

---

# 작업 목록

## 🔴 P0 (필수 작업)

### 📅 03-09 (월) — 프론트 구축 및 API 정리

- [x] Lovable로 복약지도 앱 프론트엔드 구축
- [x] Lovable 프로젝트 GitHub 레포 연결 (`yoyak-med-mentor`)
- [x] 프론트엔드 페이지 구조 생성

- [x] API 명세서 분석
- [x] 프론트 API 명세 기준 수정

수정 내용

- `/auth/*` → `/accounts/*`
- 응답 구조 `{ status, data, message }`
- 에러 구조 `{ error_code, error_detail, field_errors }`
- 성별 `M / F`
- 회원가입 필드 추가  
  - `nickname`
  - `email_token`
  - `sms_token`

- 소셜 로그인 연결  
  - Google OAuth  
  - Kakao OAuth  

수정된 파일

- `types/user.ts`
- `api/client.ts`
- `api/auth.ts`
- `contexts/AuthContext.tsx`
- `pages/Login.tsx`
- `pages/Signup.tsx`

---

### 📅 03-10 (화) — 백엔드 기능 구현

- [ ] FastAPI `/medicines/recognize` 구현
- [ ] FastAPI `/medicines/guide` 구현
- [ ] FastAPI `/medicines/tts` 구현
- [ ] 프론트 ↔ 백엔드 API 연결 테스트

---

### 📅 03-11 (수) — 기능 통합 및 웹 배포

- [ ] 복약 알림 기능 구현
- [ ] Lovable 프론트에 백엔드 URL 연결
- [ ] 웹 서비스 Vercel 배포
- [ ] 웹 서비스 기능 테스트

---

# 🚀 앱인토스 출시 스프린트

## 📅 03-12 (목) — 앱인토스 설정

- [ ] Toss Developers 콘솔 앱 생성
- [ ] 미니앱 기본 정보 등록
- [ ] WebView 서비스 URL 등록
- [ ] Toss Login 설정
- [ ] OAuth Redirect URL 설정
- [ ] 서비스 약관 / 개인정보처리방침 등록

---

## 📅 03-13 (금) — 앱인토스 테스트 및 출시

- [ ] Toss Login 동작 테스트
- [ ] WebView UI 테스트
- [ ] 복약지도 기능 테스트
- [ ] 오류 수정
- [ ] 앱인토스 미니앱 출시 제출

---

# 앱인토스 출시 체크리스트

- [ ] Toss Developers 콘솔 등록
- [ ] 서비스 이름 / 아이콘 등록
- [ ] WebView URL 연결
- [ ] Toss Login OAuth 설정
- [ ] Redirect URI 등록
- [ ] 개인정보처리방침 URL 등록
- [ ] 서비스 약관 등록
- [ ] WebView 모바일 UI 테스트
- [ ] 로그인 동작 테스트
- [ ] 출시 제출

---

# 완료 기준 (Definition of Done)

- Lovable 프론트엔드 정상 동작
- API 명세 기반 프론트–백엔드 통신 성공
- 알약 인식 → 복약지도 생성 가능
- 복약 알림 기능 동작
- 웹 서비스 배포 완료
- 앱인토스 미니앱 출시 제출 완료

---

# 스프린트 결과물

- Lovable 기반 React 프론트엔드
- GitHub 프론트 레포
- API 명세 기반 프론트–백엔드 연결
- 웹 서비스 배포
- 앱인토스 미니앱 출시
```

---

✅ 이 문서 기준으로 지금 스프린트 흐름은 이렇게 됩니다.

```
월  프론트 + API 명세 정리
화  백엔드 기능 구현
수  통합 + 웹 배포
목  앱인토스 설정
금  앱인토스 출시
```
