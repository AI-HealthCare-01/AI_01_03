# API 명세서
## REST API Documentation

---

## 문서 정보

| 항목 | 내용 |
|------|------|
| API 버전 | v1 |
| 문서 버전 | 1.1 |
| 작성일 | 2026-02-26 |
| 최종 수정일 | 2026-02-26 |
| 표준 | OpenAPI 3.0 기반 |

---

## 목차
1. [개요](#1-개요)
2. [서버 정보](#2-서버-정보)
3. [인증](#3-인증)
4. [공통 사양](#4-공통-사양)
5. [API 엔드포인트](#5-api-엔드포인트)

---

## 1. 개요

### 1.1 API 소개
본 문서는 "요약" 프로젝트의 REST API 명세를 정의합니다. 복약 관리 AI 서비스를 위한 백엔드 API의 엔드포인트, 요청/응답 형식, 인증 방법 등을 상세히 설명합니다.

### 1.2 API 설계 원칙
- **RESTful 아키텍처**: HTTP 메소드를 활용한 직관적인 API 설계
- **JSON 형식**: 모든 요청/응답은 JSON 형식 사용
- **버전 관리**: URL 경로에 버전 명시 (`/api/v1/...`)
- **보안**: JWT 기반 인증, HTTPS 필수
- **표준 HTTP 상태 코드**: 명확한 응답 상태 표현

### 1.3 API 카테고리

| 카테고리 | 설명 | 인증 필요 |
|----------|------|----------|
| 회원 관리 | 회원가입, 로그인, 토큰 갱신 등 | 부분 |
| 건강 프로필 | 개인 건강 정보 관리 | 필수 |
| 알약 식별 | Vision AI 기반 알약 인식 | 선택 |
| 처방전 OCR | 처방전 이미지 텍스트 추출 | 선택 |
| 복약 가이드 | AI 기반 맞춤형 가이드 생성 | 필수 |
| AI 챗봇 | 복약 관련 질의응답 | 선택 |
| 복약 알림 | 알림 설정 및 관리 | 필수 |
| 복약 기록 | 복약 이력 조회 및 관리 | 필수 |

---

## 2. 서버 정보

### 2.1 Base URL

| 환경 | URL | 설명 |
|------|-----|------|
| 개발 (Dev) | `https://dev-api.example.com` | 개발 환경 서버 |
| 스테이징 (Staging) | `https://staging-api.example.com` | 테스트 환경 서버 |
| 운영 (Production) | `https://api.example.com` | 실제 서비스 서버 |

### 2.2 API 버전
- **현재 버전**: v1
- **버전 표기**: URL 경로에 포함 (`/api/v1/...`)
- **하위 호환성**: 주 버전 변경 시 이전 버전 최소 6개월 유지

---

## 3. 인증

### 3.1 인증 방식
본 API는 **JWT (JSON Web Token)** 기반 인증을 사용합니다.

### 3.2 토큰 종류

| 토큰 종류 | 유효 기간 | 용도 |
|----------|----------|------|
| Access Token | 24시간 | API 요청 인증 |
| Refresh Token | 30일 | Access Token 갱신 |

### 3.3 인증 헤더 형식
```http
Authorization: Bearer {access_token}
Content-Type: application/json
```

### 3.4 토큰 획득 방법
1. 로그인 API (`POST /api/v1/accounts/login`) 호출
2. 응답으로 Access Token 및 Refresh Token 수신
3. 이후 API 요청 시 Authorization 헤더에 Access Token 포함

### 3.5 토큰 갱신
- Access Token 만료 시 Refresh Token으로 갱신
- 갱신 API: `POST /api/v1/accounts/token/refresh`

---

## 4. 공통 사양

### 4.1 요청 헤더

| 헤더 | 필수 여부 | 설명 |
|------|----------|------|
| Content-Type | 필수 | `application/json` |
| Authorization | 선택* | `Bearer {token}` (인증 필요 API만) |
| Accept | 선택 | `application/json` (기본값) |

### 4.2 공통 응답 형식

#### 성공 응답
```json
{
  "status": "success",
  "data": {
    // 응답 데이터
  },
  "message": "성공 메시지"
}
```

#### 에러 응답
```json
{
  "status": "error",
  "error_code": "ERROR_CODE",
  "error_detail": "상세 에러 메시지",
  "field_errors": {
    "field_name": "필드별 에러 메시지"
  }
}
```

### 4.3 HTTP 상태 코드

| 상태 코드 | 설명 | 사용 예시 |
|----------|------|----------|
| 200 OK | 성공 (조회, 수정, 삭제) | GET, PUT, DELETE 성공 |
| 201 Created | 리소스 생성 성공 | POST 성공 |
| 204 No Content | 성공 (응답 본문 없음) | DELETE 성공 (응답 불필요) |
| 400 Bad Request | 잘못된 요청 | 필수 필드 누락, 유효성 검증 실패 |
| 401 Unauthorized | 인증 실패 | 토큰 없음, 토큰 만료 |
| 403 Forbidden | 권한 없음 | 접근 권한 부족 |
| 404 Not Found | 리소스 없음 | 존재하지 않는 리소스 요청 |
| 409 Conflict | 리소스 충돌 | 중복 데이터 생성 시도 |
| 422 Unprocessable Entity | 처리 불가능한 엔티티 | 비즈니스 로직 검증 실패 |
| 429 Too Many Requests | 요청 횟수 초과 | Rate Limit 초과 |
| 500 Internal Server Error | 서버 내부 오류 | 예상치 못한 서버 에러 |
| 503 Service Unavailable | 서비스 이용 불가 | 서버 점검, 과부하 |

### 4.4 공통 에러 코드

| 에러 코드 | HTTP 상태 | 설명 |
|----------|----------|------|
| `INVALID_TOKEN` | 401 | 유효하지 않은 토큰 |
| `EXPIRED_TOKEN` | 401 | 만료된 토큰 |
| `MISSING_REQUIRED_FIELD` | 400 | 필수 필드 누락 |
| `INVALID_FORMAT` | 400 | 잘못된 형식 |
| `RESOURCE_NOT_FOUND` | 404 | 리소스를 찾을 수 없음 |
| `DUPLICATE_RESOURCE` | 409 | 중복된 리소스 |
| `PERMISSION_DENIED` | 403 | 권한 없음 |
| `RATE_LIMIT_EXCEEDED` | 429 | 요청 횟수 초과 |
| `INTERNAL_SERVER_ERROR` | 500 | 서버 내부 오류 |

#### 500 Internal Server Error 예시
```json
{
  "status": "error",
  "error_code": "INTERNAL_SERVER_ERROR",
  "error_detail": "서버에서 알 수 없는 오류가 발생했습니다."
}
```

### 4.5 페이징 (Pagination)

#### 페이징 요청 파라미터
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| page | integer | 1 | 페이지 번호 (1부터 시작) |
| limit | integer | 20 | 페이지당 항목 수 (최대 100) |
| sort | string | created_at | 정렬 기준 필드 |
| order | string | desc | 정렬 순서 (asc/desc) |

#### 페이징 응답 형식
```json
{
  "status": "success",
  "data": {
    "items": [...],
    "pagination": {
      "current_page": 1,
      "total_pages": 10,
      "total_items": 200,
      "items_per_page": 20,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

---

## 5. API 엔드포인트

## 5.1 회원 관리 (Authentication)

### 5.1.1 회원가입

#### 기본 정보

| 항목 | 내용 |
|------|------|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/accounts/signup` |
| **설명** | 신규 사용자 회원가입 |
| **인증 필요** | 아니오 |
| **담당자** | - |
| **상태** | 대기중 |

#### Request

##### Headers
```http
Content-Type: application/json
```

##### Query Parameters
없음

##### Request Body

**스키마**
| 필드명 | 타입 | 필수 | 제약 조건 | 설명 |
|--------|------|------|----------|------|
| email | string | O | 이메일 형식 | 사용자 이메일 |
| password | string | O | 8-20자, 영문+숫자+특수문자 | 비밀번호 |
| nickname | string | O | 2-10자 | 닉네임 |
| name | string | O | 2-20자 | 실명 |
| birthday | string | O | YYYY-MM-DD | 생년월일 |
| gender | string | O | M 또는 F | 성별 |
| email_token | string | O | - | 이메일 인증 토큰 |
| sms_token | string | O | - | SMS 인증 토큰 |

**예시**
```json
{
  "email": "user@example.com",
  "password": "Password1234@",
  "nickname": "김유저",
  "name": "홍길동",
  "birthday": "1990-11-20",
  "gender": "M",
  "email_token": "saddfj2h4u81478ssxzcv",
  "sms_token": "24yuicdfhduf128924hv"
}
```

#### Response

##### Success (201 Created)

**스키마**
```json
{
  "status": "success",
  "data": {
    "user_id": "string",
    "email": "string",
    "nickname": "string",
    "created_at": "string (ISO 8601)"
  },
  "message": "회원가입이 완료되었습니다."
}
```

**예시**
```json
{
  "status": "success",
  "data": {
    "user_id": "usr_1234567890",
    "email": "user@example.com",
    "nickname": "김유저",
    "created_at": "2026-02-26T10:30:00Z"
  },
  "message": "회원가입이 완료되었습니다."
}
```

##### Error Responses

**400 Bad Request - 필수 필드 누락**
```json
{
  "status": "error",
  "error_code": "MISSING_REQUIRED_FIELD",
  "error_detail": "필수 필드가 누락되었습니다.",
  "field_errors": {
    "nickname": "이 필드는 필수 항목입니다."
  }
}
```

**400 Bad Request - 유효성 검증 실패**
```json
{
  "status": "error",
  "error_code": "INVALID_FORMAT",
  "error_detail": "입력 형식이 올바르지 않습니다.",
  "field_errors": {
    "password": "비밀번호는 8-20자, 영문+숫자+특수문자를 포함해야 합니다.",
    "email": "올바른 이메일 형식이 아닙니다."
  }
}
```

**409 Conflict - 중복 회원**
```json
{
  "status": "error",
  "error_code": "DUPLICATE_RESOURCE",
  "error_detail": "이미 가입된 이메일입니다."
}
```

**401 Unauthorized - 인증 토큰 오류**
```json
{
  "status": "error",
  "error_code": "INVALID_TOKEN",
  "error_detail": "이메일 또는 SMS 인증 토큰이 유효하지 않습니다."
}
```

##### Status Codes
| 코드 | 설명 |
|------|------|
| 201 | 회원가입 성공 |
| 400 | 잘못된 요청 (필수 필드 누락, 유효성 검증 실패) |
| 401 | 인증 토큰 오류 |
| 409 | 중복된 이메일 또는 닉네임 |
| 500 | 서버 내부 오류 |

##### 비즈니스 로직
1. 이메일 및 SMS 인증 토큰 검증
2. 비밀번호 복잡도 검증 (8-20자, 영문+숫자+특수문자)
3. 이메일 중복 확인
4. 닉네임 중복 확인
5. 비밀번호 암호화 (bcrypt)
6. 사용자 정보 DB 저장
7. 회원가입 완료 응답 반환

---

### 5.1.2 구글 소셜 로그인

#### 기본 정보

| 항목 | 내용 |
|------|------|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/auth/google/login` |
| **설명** | 구글 OAuth 2.0 인증 시작 |
| **인증 필요** | 아니오 |
| **담당자** | - |
| **상태** | 대기중 |

#### Request

##### Headers
```http
Content-Type: application/json
```

##### Query Parameters
| 파라미터명 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| redirect_uri | string | X | /auth/google/callback | 인증 완료 후 리다이렉트 URL |

##### Request Body
없음

#### Response

##### Success (302 Redirect)

사용자를 구글 OAuth 인증 페이지로 리다이렉트합니다.

```
Location: https://accounts.google.com/o/oauth2/v2/auth?
  client_id={client_id}&
  redirect_uri={redirect_uri}&
  response_type=code&
  scope=openid%20email%20profile
```

---

### 5.1.3 구글 소셜 로그인 콜백

#### 기본 정보

| 항목 | 내용 |
|------|------|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/auth/google/callback` |
| **설명** | 구글 OAuth 인증 콜백 처리 |
| **인증 필요** | 아니오 |
| **담당자** | - |
| **상태** | 대기중 |

#### Request

##### Query Parameters
| 파라미터명 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| code | string | O | 구글로부터 받은 인증 코드 |
| state | string | X | CSRF 방지용 state 파라미터 |

#### Response

##### Success (200 OK)

**스키마**
```json
{
  "status": "success",
  "data": {
    "access_token": "string",
    "refresh_token": "string",
    "user_id": "string",
    "email": "string",
    "name": "string",
    "profile_image": "string",
    "is_new_user": "boolean"
  },
  "message": "로그인이 완료되었습니다."
}
```

**예시**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": "usr_google_1234567890",
    "email": "user@gmail.com",
    "name": "홍길동",
    "profile_image": "https://lh3.googleusercontent.com/...",
    "is_new_user": false
  },
  "message": "로그인이 완료되었습니다."
}
```

##### Error Responses

**400 Bad Request - 인증 코드 오류**
```json
{
  "status": "error",
  "error_code": "INVALID_AUTH_CODE",
  "error_detail": "유효하지 않은 인증 코드입니다."
}
```

**401 Unauthorized - 토큰 교환 실패**
```json
{
  "status": "error",
  "error_code": "TOKEN_EXCHANGE_FAILED",
  "error_detail": "구글 토큰 교환에 실패했습니다."
}
```

##### Status Codes
| 코드 | 설명 |
|------|------|
| 200 | 로그인 성공 (기존 회원 또는 신규 가입) |
| 400 | 잘못된 인증 코드 |
| 401 | 토큰 교환 실패 |
| 500 | 서버 내부 오류 |

##### 비즈니스 로직
1. 구글로부터 받은 인증 코드 검증
2. 인증 코드로 구글 액세스 토큰 교환
3. 구글 사용자 정보 조회 (email, name, profile)
4. 이메일로 기존 회원 확인
5. 신규 회원인 경우 자동 회원가입 처리
6. JWT Access Token 및 Refresh Token 발급
7. 로그인 완료 응답 반환

---

### 5.1.4 카카오 소셜 로그인

#### 기본 정보

| 항목 | 내용 |
|------|------|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/auth/kakao/login` |
| **설명** | 카카오 OAuth 2.0 인증 시작 |
| **인증 필요** | 아니오 |
| **담당자** | - |
| **상태** | 대기중 |

#### Request

##### Headers
```http
Content-Type: application/json
```

##### Query Parameters
| 파라미터명 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| redirect_uri | string | X | /auth/kakao/callback | 인증 완료 후 리다이렉트 URL |

##### Request Body
없음

#### Response

##### Success (302 Redirect)

사용자를 카카오 OAuth 인증 페이지로 리다이렉트합니다.

```
Location: https://kauth.kakao.com/oauth/authorize?
  client_id={rest_api_key}&
  redirect_uri={redirect_uri}&
  response_type=code
```

---

### 5.1.5 카카오 소셜 로그인 콜백

#### 기본 정보

| 항목 | 내용 |
|------|------|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/auth/kakao/callback` |
| **설명** | 카카오 OAuth 인증 콜백 처리 |
| **인증 필요** | 아니오 |
| **담당자** | - |
| **상태** | 대기중 |

#### Request

##### Query Parameters
| 파라미터명 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| code | string | O | 카카오로부터 받은 인증 코드 |

#### Response

##### Success (200 OK)

**스키마**
```json
{
  "status": "success",
  "data": {
    "access_token": "string",
    "refresh_token": "string",
    "user_id": "string",
    "email": "string",
    "nickname": "string",
    "profile_image": "string",
    "is_new_user": "boolean"
  },
  "message": "로그인이 완료되었습니다."
}
```

**예시**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": "usr_kakao_1234567890",
    "email": "user@kakao.com",
    "nickname": "김유저",
    "profile_image": "http://k.kakaocdn.net/...",
    "is_new_user": true
  },
  "message": "로그인이 완료되었습니다."
}
```

##### Error Responses

**400 Bad Request - 인증 코드 오류**
```json
{
  "status": "error",
  "error_code": "INVALID_AUTH_CODE",
  "error_detail": "유효하지 않은 인증 코드입니다."
}
```

**401 Unauthorized - 토큰 교환 실패**
```json
{
  "status": "error",
  "error_code": "TOKEN_EXCHANGE_FAILED",
  "error_detail": "카카오 토큰 교환에 실패했습니다."
}
```

##### Status Codes
| 코드 | 설명 |
|------|------|
| 200 | 로그인 성공 (기존 회원 또는 신규 가입) |
| 400 | 잘못된 인증 코드 |
| 401 | 토큰 교환 실패 |
| 500 | 서버 내부 오류 |

##### 비즈니스 로직
1. 카카오로부터 받은 인증 코드 검증
2. 인증 코드로 카카오 액세스 토큰 교환
3. 카카오 사용자 정보 조회 (email, nickname, profile)
4. 이메일로 기존 회원 확인 (이메일 미동의 시 카카오 ID로 확인)
5. 신규 회원인 경우 자동 회원가입 처리
6. JWT Access Token 및 Refresh Token 발급
7. 로그인 완료 응답 반환

---

## 6. API 추가 템플릿

### [API 이름]

#### 기본 정보

| 항목 | 내용 |
|------|------|
| **Method** | `GET/POST/PUT/DELETE` |
| **Endpoint** | `/api/v1/resource/...` |
| **설명** | API에 대한 간단한 설명 |
| **인증 필요** | 예/아니오 |
| **담당자** | 담당자명 |
| **상태** | 대기중/진행중/완료 |

#### Request

##### Headers
```http
Authorization: Bearer {access_token}
Content-Type: application/json
```

##### Path Parameters
| 파라미터명 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| id | integer | O | 리소스 ID |

##### Query Parameters
| 파라미터명 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| page | integer | X | 1 | 페이지 번호 |
| limit | integer | X | 20 | 페이지당 항목 수 |

##### Request Body

**스키마**
| 필드명 | 타입 | 필수 | 제약 조건 | 설명 |
|--------|------|------|----------|------|
| field1 | string | O | 최대 100자 | 필드 설명 |
| field2 | integer | X | 1-100 | 필드 설명 |

**예시**
```json
{
  "field1": "value1",
  "field2": 10
}
```

#### Response

##### Success (200 OK)

**스키마**
```json
{
  "status": "success",
  "data": {
    "field": "datatype"
  },
  "message": "성공 메시지"
}
```

**예시**
```json
{
  "status": "success",
  "data": {
    "field": "value"
  },
  "message": "요청이 성공적으로 처리되었습니다."
}
```

##### Error Responses

**400 Bad Request**
```json
{
  "status": "error",
  "error_code": "INVALID_FORMAT",
  "error_detail": "입력 형식이 올바르지 않습니다."
}
```

**401 Unauthorized**
```json
{
  "status": "error",
  "error_code": "INVALID_TOKEN",
  "error_detail": "유효하지 않은 토큰입니다."
}
```

**404 Not Found**
```json
{
  "status": "error",
  "error_code": "RESOURCE_NOT_FOUND",
  "error_detail": "요청한 리소스를 찾을 수 없습니다."
}
```

##### Status Codes
| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 |
| 401 | 인증 실패 |
| 403 | 권한 없음 |
| 404 | 리소스를 찾을 수 없음 |
| 500 | 서버 내부 오류 |

##### 비즈니스 로직
1. 단계별 처리 과정 설명
2. 검증 로직
3. 데이터 처리
4. 응답 생성

---

## 7. 부록

### 7.1 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2026-02-26 | - | 초안 작성 (OpenAPI 3.0 표준 기반) |
| 1.1 | 2026-02-26 | - | 소셜 로그인 API 추가 (구글, 카카오) |

### 7.2 참고 문서
- [OpenAPI Specification 3.0](https://swagger.io/specification/)
- [REST API 디자인 모범 사례 - Microsoft Azure](https://learn.microsoft.com/ko-kr/azure/architecture/best-practices/api-design)
- [HTTP 상태 코드 - MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Status)

### 7.3 용어 설명

| 용어 | 설명 |
|------|------|
| JWT | JSON Web Token, 사용자 인증을 위한 토큰 |
| OAuth 2.0 | 소셜 로그인 등에 사용되는 표준 인증 프로토콜 |
| REST | Representational State Transfer, 웹 서비스 아키텍처 스타일 |
| CRUD | Create, Read, Update, Delete의 약자 |
| API | Application Programming Interface |

### 7.4 개발 가이드

#### API 테스트 도구
- **Postman**: API 테스트 및 문서화
- **Swagger UI**: OpenAPI 스펙 기반 인터랙티브 문서
- **cURL**: 커맨드라인 기반 API 테스트

#### 예시: cURL 요청
```bash
# 회원가입 API 호출
curl -X POST https://api.example.com/api/v1/accounts/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "Password1234@",
    "nickname": "김유저",
    "name": "홍길동",
    "birthday": "1990-11-20",
    "gender": "M",
    "email_token": "token123",
    "sms_token": "sms456"
  }'
```

#### Rate Limiting
- **제한**: 분당 최대 60회 요청
- **초과 시**: HTTP 429 Too Many Requests 응답
- **헤더**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```
