# Sprint01 통합 계약서 (E2E 안정화용)

## 🎯 목적

* 병렬 개발 중에도 03/07 E2E가 끊기지 않도록 한다.
* API 키 / 식별자 / 실패 처리 방식을 고정한다.
* 이번 스프린트 동안 아래 계약은 변경하지 않는다.

---

# 1. 공통 규칙

## 1.1 API 응답은 JSON 고정

* 키 이름 변경 금지
* 타입 변경 금지 (string ↔ array 등)
* 필드 삭제 금지

---

## 1.2 모든 API는 공통 필드를 포함

```json
{
  "success": true,
  "error_code": null
}
```

* 실패 시 반드시 `success: false`
* 실패 시 반드시 `error_code` 값 포함

---

## 1.3 medication_id 네이밍 통일

형식:

```
영문대문자 + 언더스코어
예: TYLENOL_500
```

### 연결 규칙

* Vision → medication_id 반환
* OCR → name → medication_id 매핑
* RAG → KB에 medication_key 유지

이 키가 다르면 E2E 연결이 끊어진다.

---

# 2. Vision API 계약

## POST `/api/vision/identify`

### 성공 응답

```json
{
  "success": true,
  "candidates": [
    {
      "medication_id": "TYLENOL_500",
      "confidence": 0.93
    }
  ],
  "error_code": null
}
```

### 실패 응답

```json
{
  "success": false,
  "candidates": [],
  "error_code": "LOW_CONFIDENCE"
}
```

### 합의사항

* confidence 0.8 미만 → LOW_CONFIDENCE
* candidates는 confidence 내림차순 정렬
* 최소 1개 이상 반환 (성공 시)

---

# 3. OCR API 계약

## POST `/api/ocr/parse`

### 성공 응답

```json
{
  "success": true,
  "parsed": {
    "medications": [
      {
        "name": "타이레놀정",
        "dose_text": "1일 3회, 3일분"
      }
    ]
  },
  "error_code": null
}
```

### 실패 응답

```json
{
  "success": false,
  "parsed": null,
  "error_code": "PARSE_FAILED"
}
```

### 규칙

* medications는 배열
* 복수 약물 처방 가능성 고려

---

# 4. RAG API 계약

## POST `/api/chat`

### 성공 응답

```json
{
  "success": true,
  "answer": "",
  "sections": {
    "summary": "",
    "dosage": "",
    "precautions": "",
    "tips": ""
  },
  "tts_segments": [],
  "citations": [],
  "disclaimer": ""
}
```

### 실패 응답 (임계값 미달)

```json
{
  "success": false,
  "error_code": "LOW_RAG_CONFIDENCE"
}
```

---

## RAG 추가 규칙

* `disclaimer`는 항상 포함 (서버 강제 삽입)
* `tts_segments`는 문장 단위 배열
* `citations`는 최소 다음 필드 포함:

  * source
  * title
* 임계값 미달 시 답변 생성 금지

---

# 5. E2E 연결 흐름

1. 📷 Vision → medication_id 반환
2. 🧾 OCR → 복용 정보 파싱
3. 📚 RAG → 약 가이드 생성
4. 🔊 UI → tts_segments 순차 재생
5. 📌 화면 하단 → disclaimer 고정 표시

---

# 6. 통합 게이트 (03/05 이전 필수)

* [ ] 각 API mock JSON 공유
* [ ] medication_id 통일 확인
* [ ] 실패 응답 구조 통일
* [ ] 키 누락 시 서버 validation 적용

---

# 7. 변경 원칙

* 스프린트 중 계약 변경 필요 시:

  1. 전원 합의
  2. 본 문서 업데이트
  3. 코드 수정

문서 수정 없이 API 변경 금지.

---

**이 문서 기준으로 Sprint01 통합을 진행한다.**
