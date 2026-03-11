> 상태: 초안 (Draft)  
> 본 문서는 Vision 검수/재학습 구조 논의를 위한 내부 초안이며, 팀 합의 후 확정본으로 전환한다.

# Vision Review DB Schema

이 문서는 Vision 운영 샘플/검수 큐/사람 검수 결과를 파일(JSONL) 기준이 아닌 **DB 테이블 기준**으로 정의한다.  
목표는 검수 의미 충돌을 방지하고, 재학습 후보 편입 기준을 일관되게 적용하는 것이다.

---

## 1. 문서 목적

Vision `/api/vision/identify` 운영 데이터 관리를 다음 3개 테이블로 표준화한다.

1. `vision_samples`: 추론 원본 로그
2. `vision_review_queue`: 자동 검수 우선순위 큐
3. `vision_review_results`: 사람 검수 최종 결과

---

## 2. 테이블 역할

## 2-1. `vision_samples`
- 추론 요청 1건의 원본 메타/결과 저장소
- 기존 `records.jsonl` 역할을 대체
- 운영 분석/검수/재학습의 기준 데이터

## 2-2. `vision_review_queue`
- 검수 우선순위 산정 결과 저장
- 기존 `review_queue.jsonl` 역할을 대체
- 검수 작업 순서 제어용

## 2-3. `vision_review_results`
- 사람 검수 판정 및 재학습 편입 판단 저장
- 기존 `review_results.jsonl` 역할을 대체
- 모델 개선 루프의 최종 기준 데이터

---

## 3. 테이블별 주요 컬럼 (최소안)

## 3-1. `vision_samples` 주요 컬럼
- `sample_id` (UNIQUE,pk 전 구간 공통 키)
- `created_at`
- `request_endpoint`
- `source_type`
- `original_image_path`
- `content_type`
- `image_size_bytes`
- `success`
- `error_code`
- `predicted_candidates_json`
- `top1_medication_id`
- `top1_confidence`
- `detection_boxes_json`
- `raw_detections_json`
- `model_version_detect`
- `model_version_classify`

## 3-2. `vision_review_queue` 주요 컬럼
- `sample_id` (FK to `vision_samples.sample_id`)
- `review_priority` (`P0|P1|P2|P3|P4`)
- `review_reason_codes_json` (복수 사유 허용)
- `review_status` (`pending|in_progress|done`)
- `generated_at`

## 3-3. `vision_review_results` 주요 컬럼
- `sample_id` (FK to `vision_samples.sample_id`)
- `review_status` (`approved|rejected|needs_info`)
- `ground_truth_medication_id`
- `retrain_eligible` (`true|false`)
- `retrain_bucket` (`detect|classify|both|none`)
- `reviewer`
- `reviewed_at`
- `decision_reason_codes_json` (복수 사유 허용)
- `queue_reason_codes_json` (선택)
- `review_note` (선택)

---

## 4. 핵심 정책

## 4-1. 공통 키 정책
- `sample_id`를 `vision_samples` / `vision_review_queue` / `vision_review_results`의 공통 연결 키로 사용한다.

## 4-2. 판정 의미 분리 정책
- `review_status`: 검수 판정 상태
- `retrain_eligible`: 재학습 편입 가능 여부
- 즉, `review_status='approved'`여도 `retrain_eligible=false` 가능

## 4-3. 사유 코드 분리 정책
- Queue: `review_reason_codes_json` = 자동 우선순위 산정 사유
- Results: `decision_reason_codes_json` = 사람 최종 판정 사유

## 4-4. 최신 1건 유효 정책 (`sample_id` 기준)
- `vision_review_results`는 원칙적으로 **sample_id당 최신 1건만 유효**로 본다.
- 기준:
  1. `reviewed_at` 최신값 우선
  2. 동일 시각 충돌 시, `id`가 더 큰 레코드 우선
- 검수 이력 다건 관리/병합은 후속 단계로 미룬다.

---

## 5. 검수/재학습 연결 흐름

1. API 추론 완료 → `vision_samples` 저장
2. 배치/스크립트로 우선순위 계산 → `vision_review_queue` 생성/갱신
3. 사람이 검수 수행 → `vision_review_results` 저장 (sample_id 기준 최신 1건 유효)
4. 재학습 후보 선정 시 `vision_samples + vision_review_results`를 `sample_id`로 조인
5. `retrain_eligible=true` 및 `retrain_bucket` 기준으로 detect/classify 후보셋 분리

---

## 6. 구현 순서 (코치님 가이드 1~6)

1. 문서/스키마 확정 (현재 단계)
2. 모델 추가 (`vision_samples`, `vision_review_queue`, `vision_review_results`)
3. 마이그레이션 생성 및 SQL 검토
4. 마이그레이션 적용 (dev 환경)
5. API 경로 dual-write 적용 (파일 + DB 병행)
6. 큐/검수결과를 DB 기준으로 전환 후 파일 의존 축소

---

## 7. 이번 단계 범위

- 포함: DB 기준 문서/스키마 확정
- 제외: 모델 생성, 마이그레이션 생성, 코드 반영, 데이터 이관

---

## 8. 파일명 제안

현재 파일: `VISION_REVIEW_SCHEMA_DRAFT.md`  
권장 파일명(가독성): `VISION_REVIEW_DB_SCHEMA_DRAFT.md`

(이번 단계에서는 내용만 DB 기준으로 전환하고, 파일명 변경은 팀 합의 후 적용)
