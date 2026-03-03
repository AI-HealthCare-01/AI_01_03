---
tags: [API, 명세서, 요약, 아키텍처, 백엔드]
작성일: 2026-02-23
수정일: 2026-02-23
버전: v1.0
상태: 진행중
base_url: https://api.yoyak.app
---

# 🌐 API 명세서

> 상위 문서: [[🏠 요약 - 프로젝트 홈]] | [[시스템 아키텍처 설계]] | [[ERD - 데이터베이스 설계]]

---

## 📋 관련 문서 (Dataview)

```dataview
table 상태, 버전
from "20-프로젝트/21-진행중/요약/03-기술아키텍처"
where contains(tags, "아키텍처")
sort file.name asc
```

---

## 1. API 개요

### 1.1 Base URL
- **Production**: `https://api.yoyak.app`
- **Staging**: `https://staging-api.yoyak.app`
- **Development**: `http://localhost:3000`

### 1.2 인증 방식
- **JWT (JSON Web Token)** 기반 인증
- **Header**: `Authorization: Bearer {token}`
- **Token 유효기간**: 24시간
- **Refresh Token**: 30일

### 1.3 공통 응답 형식
```json
// 성공
{
  "success": true,
  "data": { ... },
  "message": "요청이 성공적으로 처리되었습니다."
}

// 실패
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "에러 메시지",
    "details": { ... }
  }
}
```

### 1.4 공통 에러 코드
| 코드 | 상태 | 설명 |
|------|------|------|
| `UNAUTHORIZED` | 401 | 인증 실패 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `VALIDATION_ERROR` | 400 | 입력값 검증 실패 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |
| `RATE_LIMIT_EXCEEDED` | 429 | 요청 제한 초과 |

---

## 2. 인증 API

### 2.1 회원가입
```http
POST /api/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123!",
  "name": "홍길동",
  "phone": "010-1234-5678",
  "birthDate": "1990-01-01",
  "gender": "MALE",
  "role": "PATIENT"
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "userId": "uuid-v4",
    "email": "user@example.com",
    "name": "홍길동",
    "role": "PATIENT",
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

**에러:**
- `EMAIL_ALREADY_EXISTS` (400): 이미 가입된 이메일
- `WEAK_PASSWORD` (400): 비밀번호 강도 부족 (8자 이상, 특수문자 포함)

---

### 2.2 로그인
```http
POST /api/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123!"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "userId": "uuid-v4",
    "email": "user@example.com",
    "name": "홍길동",
    "role": "PATIENT",
    "isSeniorMode": false,
    "accessToken": "...",
    "refreshToken": "..."
  }
}
```

---

### 2.3 토큰 갱신
```http
POST /api/auth/refresh
```

**Request Body:**
```json
{
  "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "accessToken": "new_access_token",
    "refreshToken": "new_refresh_token"
  }
}
```

---

## 3. 약품 정보 API

### 3.1 식약처 e약은요 검색 (1단계)
```http
POST /api/mfds/search
```

**설명:** 서버 전용 API 라우트. 환경변수 `MFDS_EYAK_SERVICE_KEY` 사용 (절대 프론트엔드 노출 금지)

**Request Body:**
```json
{
  "itemName": "타이레놀"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "itemSeq": "200808123",
        "itemName": "타이레놀정500밀리그램",
        "entpName": "한국얀센",
        "efcyQesitm": "해열·진통제 (두통, 치통, 월경통, 근육통...)",
        "useMethodQesitm": "성인 1회 1~2정, 1일 3~4회 복용. 복용 간격 4시간 이상...",
        "intrcQesitm": "다른 해열·진통제와 병용 금지. 음주 시 간 손상 위험...",
        "seQesitm": "구역, 구토, 발진, 소화불량...",
        "depositMethodQesitm": "실온(1~30℃) 보관",
        "itemImage": "https://nedrug.mfds.go.kr/..."
      }
      // ...최대 5개
    ],
    "totalCount": 15
  }
}
```

**에러:**
- `MFDS_API_ERROR` (502): 식약처 API 호출 실패
- `NO_RESULTS` (404): 검색 결과 없음

---

### 3.2 약품 상세 조회
```http
GET /api/medications/:medicationId
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "medicationId": "uuid-v4",
    "itemSeq": "200808123",
    "itemName": "타이레놀정500밀리그램",
    "entpName": "한국얀센",
    "ingredient": "아세트아미노펜",
    "classification": "OTC",
    "efcyQesitm": "해열·진통제...",
    "useMethodQesitm": "성인 1회 1~2정...",
    "intrcQesitm": "다른 해열·진통제와 병용 금지...",
    "seQesitm": "구역, 구토, 발진...",
    "depositMethodQesitm": "실온 보관",
    "itemImage": "https://...",
    "isVerified": true,
    "lastSyncedAt": "2026-02-23T10:00:00Z"
  }
}
```

---

### 3.3 약품 검색 (자동완성)
```http
GET /api/medications/search?q={query}&limit=10
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "medicationId": "uuid-v4",
        "itemName": "타이레놀정500밀리그램",
        "entpName": "한국얀센",
        "itemImage": "https://..."
      }
      // ...
    ]
  }
}
```

---

## 4. 처방전 관리 API

### 4.1 처방전 업로드 (OCR)
```http
POST /api/prescriptions/upload
```

**Request (multipart/form-data):**
```
image: [File]
userId: "uuid-v4"
uploadSource: "USER_SCAN"
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "prescriptionId": "uuid-v4",
    "imageUrl": "https://s3.amazonaws.com/...",
    "ocrResult": {
      "ocrId": "uuid-v4",
      "status": "SUCCESS",
      "confidenceScore": 0.95,
      "parsedData": {
        "hospitalName": "서울대학교병원",
        "issueDate": "2026-02-20",
        "items": [
          {
            "medicationName": "타이레놀정500밀리그램",
            "dosage": "1회 1정",
            "frequency": "1일 3회",
            "durationDays": 7,
            "timingType": "AFTER_MEAL",
            "timingDetail": "식후 30분"
          }
        ]
      }
    },
    "prescriptionItems": [
      {
        "itemId": "uuid-v4",
        "medicationId": "uuid-v4",
        "medicationNameRaw": "타이레놀정500밀리그램",
        "dosage": "1회 1정",
        "frequency": "1일 3회",
        "durationDays": 7,
        "timingType": "AFTER_MEAL",
        "timingDetail": "식후 30분",
        "confidenceScore": 0.95
      }
    ]
  }
}
```

**에러:**
- `OCR_FAILED` (500): OCR 처리 실패
- `IMAGE_TOO_LARGE` (400): 이미지 크기 초과 (최대 10MB)
- `INVALID_IMAGE_FORMAT` (400): 지원하지 않는 이미지 형식

---

### 4.2 처방전 목록 조회
```http
GET /api/prescriptions?userId={userId}&page=1&limit=20
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "prescriptions": [
      {
        "prescriptionId": "uuid-v4",
        "imageUrl": "https://...",
        "imageThumbnailUrl": "https://...",
        "issueDate": "2026-02-20",
        "hospitalName": "서울대학교병원",
        "pharmacyName": "서울약국",
        "itemCount": 3,
        "createdAt": "2026-02-20T14:30:00Z"
      }
      // ...
    ],
    "pagination": {
      "currentPage": 1,
      "totalPages": 5,
      "totalCount": 100,
      "limit": 20
    }
  }
}
```

---

### 4.3 처방전 상세 조회
```http
GET /api/prescriptions/:prescriptionId
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "prescriptionId": "uuid-v4",
    "userId": "uuid-v4",
    "imageUrl": "https://...",
    "issueDate": "2026-02-20",
    "hospitalName": "서울대학교병원",
    "pharmacyName": "서울약국",
    "items": [
      {
        "itemId": "uuid-v4",
        "medication": {
          "medicationId": "uuid-v4",
          "itemName": "타이레놀정500밀리그램",
          "itemImage": "https://..."
        },
        "dosage": "1회 1정",
        "frequency": "1일 3회",
        "durationDays": 7,
        "timingType": "AFTER_MEAL",
        "instructions": "물과 함께 복용",
        "warnings": "음주 시 간 손상 위험"
      }
      // ...
    ],
    "ocrResult": {
      "status": "SUCCESS",
      "confidenceScore": 0.95
    }
  }
}
```

---

## 5. 알약 식별 API (Vision AI)

### 5.1 알약 촬영 및 식별
```http
POST /api/vision/identify
```

**Request (multipart/form-data):**
```
image: [File]
userId: "uuid-v4"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "visionId": "uuid-v4",
    "imageUrl": "https://s3.amazonaws.com/...",
    "detectedMedication": {
      "medicationId": "uuid-v4",
      "itemName": "타이레놀정500밀리그램",
      "ingredient": "아세트아미노펜",
      "itemImage": "https://...",
      "confidenceScore": 0.92
    },
    "alternativeCandidates": [
      {
        "medicationId": "uuid-v4",
        "itemName": "타이레놀이알서방정650밀리그램",
        "confidenceScore": 0.78
      }
    ]
  }
}
```

**에러:**
- `VISION_API_ERROR` (502): GLM-5 Vision API 호출 실패
- `NO_PILL_DETECTED` (404): 이미지에서 알약을 찾을 수 없음
- `LOW_CONFIDENCE` (422): 신뢰도가 너무 낮음 (< 0.7)

---

### 5.2 Vision 결과 이력 조회
```http
GET /api/vision/history?userId={userId}&page=1&limit=20
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "visionId": "uuid-v4",
        "imageUrl": "https://...",
        "detectedName": "타이레놀정500밀리그램",
        "confidenceScore": 0.92,
        "createdAt": "2026-02-23T10:00:00Z"
      }
      // ...
    ],
    "pagination": { ... }
  }
}
```

---

## 6. 복약 스케줄 API

### 6.1 스케줄 생성
```http
POST /api/schedules
```

**Request Body:**
```json
{
  "prescriptionItemId": "uuid-v4",
  "userId": "uuid-v4",
  "createdBy": "uuid-v4",  // 보호자가 대신 생성 시 guardian_id
  "scheduledTime": "2026-02-24T08:00:00Z",
  "notificationEnabled": true
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "scheduleId": "uuid-v4",
    "prescriptionItemId": "uuid-v4",
    "userId": "uuid-v4",
    "createdBy": "uuid-v4",
    "scheduledTime": "2026-02-24T08:00:00Z",
    "status": "PENDING",
    "notificationEnabled": true,
    "medication": {
      "itemName": "타이레놀정500밀리그램",
      "dosage": "1회 1정"
    }
  }
}
```

---

### 6.2 스케줄 최적화 (5단계: 골든타임 스케줄러)
```http
POST /api/schedules/optimize
```

**Request Body:**
```json
{
  "userId": "uuid-v4",
  "prescriptionItemIds": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "optimizationId": "uuid-v4",
    "originalSchedules": [
      {
        "scheduleId": "uuid-1",
        "scheduledTime": "2026-02-24T08:00:00Z",
        "medicationName": "약 A"
      },
      {
        "scheduleId": "uuid-2",
        "scheduledTime": "2026-02-24T08:30:00Z",
        "medicationName": "약 B"
      }
    ],
    "optimizedSchedules": [
      {
        "scheduleId": "uuid-1",
        "scheduledTime": "2026-02-24T08:00:00Z",
        "medicationName": "약 A"
      },
      {
        "scheduleId": "uuid-2",
        "scheduledTime": "2026-02-24T10:00:00Z",  // 2시간 간격으로 조정
        "medicationName": "약 B",
        "optimizationNote": "약 A와의 상호작용을 고려하여 2시간 간격 유지"
      }
    ],
    "conflictsDetected": [
      {
        "type": "TIME_TOO_CLOSE",
        "severity": "MEDIUM",
        "drugs": ["약 A", "약 B"],
        "description": "두 약물의 복용 시간이 30분 간격으로 너무 가깝습니다.",
        "recommendation": "최소 2시간 간격을 두고 복용하세요."
      }
    ]
  }
}
```

---

### 6.3 충돌 감지
```http
GET /api/schedules/conflicts?userId={userId}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "conflicts": [
      {
        "type": "TIME_OVERLAP",
        "severity": "HIGH",
        "schedules": [
          {
            "scheduleId": "uuid-1",
            "medicationName": "약 A",
            "scheduledTime": "2026-02-24T08:00:00Z"
          },
          {
            "scheduleId": "uuid-2",
            "medicationName": "약 B",
            "scheduledTime": "2026-02-24T08:15:00Z"
          }
        ],
        "description": "두 약물의 복용 시간이 15분 차이로 너무 가깝습니다.",
        "recommendation": "약 B를 10:00으로 변경하는 것을 권장합니다."
      }
    ]
  }
}
```

---

### 6.4 스케줄 목록 조회
```http
GET /api/schedules?userId={userId}&status=PENDING&from=2026-02-24&to=2026-02-28
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "schedules": [
      {
        "scheduleId": "uuid-v4",
        "medication": {
          "itemName": "타이레놀정500밀리그램",
          "itemImage": "https://..."
        },
        "scheduledTime": "2026-02-24T08:00:00Z",
        "status": "PENDING",
        "dosage": "1회 1정",
        "instructions": "식후 30분",
        "notificationEnabled": true,
        "createdBy": {
          "userId": "uuid-v4",
          "name": "홍길동",
          "relationship": "본인"  // 또는 "보호자 (자녀)"
        }
      }
      // ...
    ]
  }
}
```

---

### 6.5 복약 완료 처리
```http
PUT /api/schedules/:scheduleId/complete
```

**Request Body:**
```json
{
  "notedBy": "uuid-v4",  // 환자 본인 또는 보호자
  "action": "TAKEN",
  "note": "부작용 없음",
  "takenAt": "2026-02-24T08:05:00Z"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "scheduleId": "uuid-v4",
    "status": "COMPLETED",
    "log": {
      "logId": "uuid-v4",
      "action": "TAKEN",
      "note": "부작용 없음",
      "takenAt": "2026-02-24T08:05:00Z",
      "notedBy": {
        "userId": "uuid-v4",
        "name": "홍길동"
      }
    }
  }
}
```

---

## 7. 가족 관리 API

### 7.1 가족 연결 요청
```http
POST /api/family/invite
```

**Request Body:**
```json
{
  "guardianId": "uuid-v4",
  "patientEmail": "patient@example.com",  // 또는 patientPhone
  "relationshipType": "CHILD",
  "canManageMedication": true,
  "receiveMissedAlerts": true,
  "receiveEmergencyAlerts": true
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "relationId": "uuid-v4",
    "guardianId": "uuid-v4",
    "patientId": "uuid-v4",
    "relationshipType": "CHILD",
    "status": "PENDING",
    "permissions": {
      "canManageMedication": true,
      "receiveMissedAlerts": true,
      "receiveEmergencyAlerts": true
    }
  }
}
```

---

### 7.2 가족 연결 수락/거절
```http
PUT /api/family/:relationId/respond
```

**Request Body:**
```json
{
  "action": "ACCEPT"  // 또는 "REJECT"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "relationId": "uuid-v4",
    "status": "ACTIVE",
    "guardian": {
      "userId": "uuid-v4",
      "name": "홍길동",
      "email": "guardian@example.com"
    },
    "patient": {
      "userId": "uuid-v4",
      "name": "홍부모",
      "email": "patient@example.com"
    }
  }
}
```

---

### 7.3 보호자가 관리하는 환자 목록
```http
GET /api/family/patients?guardianId={guardianId}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "patients": [
      {
        "relationId": "uuid-v4",
        "patient": {
          "userId": "uuid-v4",
          "name": "홍부모",
          "birthDate": "1950-01-01",
          "isSeniorMode": true
        },
        "relationshipType": "PARENT",
        "permissions": {
          "canManageMedication": true,
          "receiveMissedAlerts": true
        },
        "recentActivity": {
          "upcomingSchedules": 3,
          "missedDoses": 1,
          "activeWarnings": 2
        }
      }
      // ...
    ]
  }
}
```

---

### 7.4 보호자 활동 로그 조회
```http
GET /api/family/:relationId/actions?page=1&limit=20
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "actions": [
      {
        "actionId": "uuid-v4",
        "actionType": "CREATE_SCHEDULE",
        "guardian": {
          "name": "홍길동"
        },
        "patient": {
          "name": "홍부모"
        },
        "details": {
          "medicationName": "타이레놀정500밀리그램",
          "scheduledTime": "2026-02-24T08:00:00Z"
        },
        "createdAt": "2026-02-23T15:30:00Z"
      }
      // ...
    ],
    "pagination": { ... }
  }
}
```

---

## 8. 상호작용 경고 API

### 8.1 사용자 경고 목록 (2단계)
```http
GET /api/warnings?userId={userId}&severity=HIGH&acknowledged=false
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "warnings": [
      {
        "warningId": "uuid-v4",
        "severity": "HIGH",
        "type": "DRUG_DRUG",
        "title": "타이레놀 + 아스피린 병용 주의",
        "description": "두 약물의 병용 시 출혈 위험이 증가할 수 있습니다.",
        "recommendedAction": "의사와 상담 필요. 복용 간격을 2시간 이상 두세요.",
        "medications": [
          {
            "itemName": "타이레놀정500밀리그램",
            "itemImage": "https://..."
          },
          {
            "itemName": "아스피린장용정100밀리그램",
            "itemImage": "https://..."
          }
        ],
        "sourceSnippet": "다른 해열·진통제와 병용 시 위장관 출혈 위험 증가...",
        "isAcknowledged": false,
        "createdAt": "2026-02-23T10:00:00Z"
      }
      // ...
    ]
  }
}
```

---

### 8.2 경고 확인 처리
```http
PUT /api/warnings/:warningId/acknowledge
```

**Request Body:**
```json
{
  "acknowledgedBy": "uuid-v4"  // 환자 또는 보호자
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "warningId": "uuid-v4",
    "isAcknowledged": true,
    "acknowledgedAt": "2026-02-23T15:30:00Z",
    "acknowledgedBy": {
      "userId": "uuid-v4",
      "name": "홍길동"
    }
  }
}
```

---

## 9. DUR 체크 API (4단계)

### 9.1 DUR 상호작용 체크
```http
POST /api/dur/check
```

**Request Body:**
```json
{
  "userId": "uuid-v4",
  "medicationIds": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "interactions": [
      {
        "interactionId": "uuid-v4",
        "drugA": {
          "medicationId": "uuid-1",
          "itemName": "약 A"
        },
        "drugB": {
          "medicationId": "uuid-2",
          "itemName": "약 B"
        },
        "contraindicationType": "DRUG_DRUG",
        "severity": "HIGH",
        "riskDescription": "두 약물의 병용 시 QT 간격 연장 위험 증가",
        "recommendedAction": "대체 약물 고려 또는 심전도 모니터링 필요",
        "source": "식약처 DUR"
      }
      // ...
    ],
    "totalInteractions": 2,
    "highRiskCount": 1,
    "mediumRiskCount": 1,
    "lowRiskCount": 0
  }
}
```

---

### 9.2 DUR 대시보드
```http
GET /api/dur/dashboard?userId={userId}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "summary": {
      "totalMedications": 5,
      "totalInteractions": 3,
      "criticalWarnings": 1,
      "highWarnings": 2,
      "mediumWarnings": 0
    },
    "criticalInteractions": [
      {
        "drugA": "약 A",
        "drugB": "약 B",
        "severity": "CRITICAL",
        "riskDescription": "병용 금기",
        "recommendedAction": "즉시 의사와 상담"
      }
    ],
    "recommendedActions": [
      "약 A와 약 B는 병용 금기입니다. 의사와 상담하세요.",
      "약 C는 식전 30분에 복용하세요."
    ]
  }
}
```

---

## 10. AI 가이드 및 챗봇 API

### 10.1 RAG 기반 가이드 생성 (3단계)
```http
GET /api/guide/:medicationId
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "medicationId": "uuid-v4",
    "itemName": "타이레놀정500밀리그램",
    "guide": {
      "summary": "타이레놀은 해열·진통제로, 두통, 치통, 근육통 등에 사용됩니다.",
      "howToUse": "성인은 1회 1~2정, 1일 3~4회 복용하세요. 복용 간격은 최소 4시간 이상 유지하세요.",
      "warnings": [
        "하루 최대 8정(4000mg)을 초과하지 마세요.",
        "음주 시 간 손상 위험이 있으니 주의하세요.",
        "다른 해열·진통제와 병용하지 마세요."
      ],
      "sideEffects": [
        "구역, 구토",
        "발진, 가려움증",
        "소화불량"
      ],
      "storage": "실온(1~30℃)에서 보관하세요."
    },
    "ragSources": [
      {
        "chunkId": "uuid-v4",
        "sourceField": "efcy",
        "snippet": "이 약은 두통, 치통, 월경통, 근육통...",
        "score": 0.95
      }
      // ...
    ]
  }
}
```

---

### 10.2 AI 챗봇 대화
```http
POST /api/chat
```

**Request Body:**
```json
{
  "userId": "uuid-v4",
  "message": "타이레놀 먹고 커피 마셔도 되나요?",
  "context": {
    "medicationIds": ["uuid-v4"]  // 현재 복용 중인 약
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "chatId": "uuid-v4",
    "userMessage": "타이레놀 먹고 커피 마셔도 되나요?",
    "aiResponse": "타이레놀(아세트아미노펜)과 커피는 일반적으로 함께 복용해도 문제가 없습니다. 오히려 커피의 카페인 성분이 진통 효과를 약간 높일 수 있습니다. 다만, 과도한 카페인 섭취는 불안감이나 불면증을 유발할 수 있으니 적당량을 섭취하세요.",
    "ragContext": [
      {
        "chunkId": "uuid-v4",
        "source": "식약처 e약은요",
        "snippet": "아세트아미노펜은 카페인과 병용 시 진통 효과 증가...",
        "score": 0.88
      }
    ],
    "confidenceScore": 0.92,
    "disclaimer": "본 정보는 참고용이며, 의사 또는 약사와 상담하세요."
  }
}
```

**에러:**
- `RAG_RETRIEVAL_FAILED` (500): RAG 검색 실패
- `LLM_API_ERROR` (502): GLM-5 LLM API 호출 실패
- `LOW_CONFIDENCE_RESPONSE` (422): 응답 신뢰도 낮음 (< 0.7) → "전문가 상담 권장" 안내

---

### 10.3 챗봇 대화 이력
```http
GET /api/chat/history?userId={userId}&page=1&limit=20
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "chatId": "uuid-v4",
        "userMessage": "타이레놀 먹고 커피 마셔도 되나요?",
        "aiResponse": "타이레놀과 커피는 일반적으로...",
        "createdAt": "2026-02-23T10:00:00Z"
      }
      // ...
    ],
    "pagination": { ... }
  }
}
```

---

## 11. 알림 API

### 11.1 알림 목록 조회
```http
GET /api/notifications?userId={userId}&isRead=false&type=MEDICATION_REMINDER
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "notificationId": "uuid-v4",
        "type": "MEDICATION_REMINDER",
        "title": "복약 시간입니다",
        "message": "타이레놀정 1회 1정을 복용하세요.",
        "relatedScheduleId": "uuid-v4",
        "isRead": false,
        "sentAt": "2026-02-24T08:00:00Z"
      },
      {
        "notificationId": "uuid-v4",
        "type": "GUARDIAN_ALERT",
        "title": "복약 미이행 알림",
        "message": "홍부모님이 오전 8시 타이레놀을 복용하지 않았습니다.",
        "relatedScheduleId": "uuid-v4",
        "isRead": false,
        "sentAt": "2026-02-24T09:00:00Z"
      }
      // ...
    ],
    "unreadCount": 5
  }
}
```

---

### 11.2 알림 읽음 처리
```http
PUT /api/notifications/:notificationId/read
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "notificationId": "uuid-v4",
    "isRead": true,
    "readAt": "2026-02-24T09:15:00Z"
  }
}
```

---

### 11.3 알림 전체 읽음 처리
```http
PUT /api/notifications/read-all
```

**Request Body:**
```json
{
  "userId": "uuid-v4"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "updatedCount": 12
  }
}
```

---

## 12. 응급 카드 API

### 12.1 응급 카드 조회
```http
GET /api/emergency-card/:userId
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "cardId": "uuid-v4",
    "user": {
      "name": "홍길동",
      "birthDate": "1950-01-01",
      "bloodType": "A"
    },
    "emergencyContacts": [
      {
        "name": "홍자녀",
        "relation": "자녀",
        "phone": "010-1234-5678"
      }
    ],
    "chronicDiseasesSummary": "당뇨, 고혈압",
    "allergiesSummary": "페니실린 알레르기",
    "currentMedicationsSummary": "타이레놀정, 아스피린장용정",
    "qrCodeUrl": "https://s3.amazonaws.com/.../qr-code.png",
    "isPublic": true
  }
}
```

---

### 12.2 응급 카드 업데이트
```http
PUT /api/emergency-card/:userId
```

**Request Body:**
```json
{
  "emergencyContacts": [
    {
      "name": "홍자녀",
      "relation": "자녀",
      "phone": "010-1234-5678"
    }
  ],
  "isPublic": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "cardId": "uuid-v4",
    "updatedAt": "2026-02-23T15:30:00Z"
  }
}
```

---

## 13. 약사 전용 API

### 13.1 환자 검색 (약사용)
```http
GET /api/pharmacist/patients/search?name={name}&birthDate={birthDate}
```

**인증:** 약사 권한 필요 (`role: PHARMACIST`)

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "patients": [
      {
        "userId": "uuid-v4",
        "name": "홍길동",
        "birthDate": "1990-01-01",
        "phone": "010-****-5678",
        "recentPrescriptions": 3
      }
    ]
  }
}
```

---

### 13.2 약사 푸시 발송
```http
POST /api/pharmacist/push
```

**Request Body:**
```json
{
  "pharmacistId": "uuid-v4",
  "patientId": "uuid-v4",
  "prescriptionId": "uuid-v4",
  "message": "처방된 약이 준비되었습니다. 복약 지도 내용을 확인하세요.",
  "customGuide": {
    "title": "복약 안내",
    "content": "타이레놀은 식후 30분에 복용하세요. 하루 최대 8정을 넘지 마세요."
  }
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "notificationId": "uuid-v4",
    "sentAt": "2026-02-23T15:30:00Z",
    "patient": {
      "userId": "uuid-v4",
      "name": "홍길동"
    }
  }
}
```

---

## 14. 헬스 체크 및 메타 API

### 14.1 헬스 체크
```http
GET /api/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-23T15:30:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "s3": "healthy",
    "mfdsApi": "healthy",
    "glm5Api": "healthy"
  }
}
```

---

### 14.2 API 버전 정보
```http
GET /api/version
```

**Response (200 OK):**
```json
{
  "version": "1.0.0",
  "buildDate": "2026-02-23",
  "environment": "production"
}
```

---

## 15. Rate Limiting

| 엔드포인트 | 제한 |
|------------|------|
| `/api/auth/*` | 10 req/min per IP |
| `/api/mfds/*` | 60 req/hour per user |
| `/api/vision/*` | 30 req/hour per user |
| `/api/chat` | 100 req/hour per user |
| 일반 API | 1000 req/hour per user |

---

## 16. Webhook (추후 확장)

### 16.1 처방전 처리 완료 Webhook
```http
POST {callback_url}
```

**Payload:**
```json
{
  "event": "prescription.processed",
  "prescriptionId": "uuid-v4",
  "userId": "uuid-v4",
  "status": "SUCCESS",
  "timestamp": "2026-02-23T15:30:00Z"
}
```

---

## 📚 관련 문서

- [[ERD - 데이터베이스 설계]]
- [[시스템 아키텍처 설계]]
- [[P0 - MVP 핵심기능]]
- [[데이터 전략 및 보안]]

---

*최종 수정: 2026-02-23 | 버전: v1.0 | 작성자: 백엔드 아키텍트*
