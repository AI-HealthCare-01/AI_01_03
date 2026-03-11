# Vision 검수 우선순위 규칙 (초안)

## 목적
- `runs/vision_samples/records.jsonl` 기반으로 실제 검수 대상을 자동 추출한다.
- 운영 이슈(P0)와 모델 개선 대상(P1~P3)을 우선 처리한다.
- `review_queue.jsonl`은 기본적으로 검수 대상만 담기도록 `P0~P3`만 포함한다.

## 입력/출력
- 입력: `runs/vision_samples/records.jsonl`
- 출력: `runs/vision_samples/review_queue.jsonl`
- 기본 동작: `P0~P3`만 출력 (`P4`는 큐 제외)
- 옵션: 필요 시 `--include-p4`로 `P4` 포함 가능

## 우선순위 기준
- `P0`: 운영 장애성 실패
  - `VISION_INTERNAL_ERROR`, `VISION_TIMEOUT`, `VISION_UPSTREAM_ERROR`
- `P1`: 탐지 누락
  - `NO_PILL_DETECTED`
- `P2`: 신뢰도 실패
  - `LOW_CONFIDENCE`
  - 기타 실패인데 분류되지 않는 경우 `UNKNOWN_FAILURE`
- `P3`: 성공했지만 검수 가치가 높은 경계 케이스
  - `top1_confidence < 0.90` (`BORDERLINE_CONFIDENCE`)
  - `top1_medication_id == UNKNOWN_PILL`
  - 후보 margin(top1-top2) `< 0.15` (`LOW_MARGIN`)
- `P4`: 나머지 성공 케이스 (기본 큐 제외)

## review_reason_codes 정책
- `review_reason_codes`는 **배열**이며, 복수 사유를 동시에 저장한다.
- 예시:
  - `LOW_CONFIDENCE` + `LOW_MARGIN`
  - `NO_PILL_DETECTED` + `UNKNOWN_FAILURE`(예외 케이스)
- 우선순위는 사유 중 가장 높은 우선순위(P0이 최상)로 결정한다.

## 방어적 파싱 원칙
- `predicted_candidates`, `top1_medication_id`, `top1_confidence`가 누락/빈값이어도 스크립트는 중단되지 않는다.
- 누락 시 기본값 처리:
  - `predicted_candidates`: `[]`
  - `top1_medication_id`: `None`
  - `top1_confidence`: `0.0`
- margin 계산은 후보 2개 미만이면 `None`으로 둔다.

## 검수 절차 (운영)
1. `build_review_queue.py` 실행하여 `review_queue.jsonl` 생성
2. `P0 → P1 → P2 → P3` 순으로 검수
3. 검수자는 샘플별 정답/오류 원인 기록
4. 재학습 편입 후보를 `detect/classify/both/none`으로 분류

## 재학습 편입 판단 기준(초기)
- 탐지 데이터셋 편입:
  - `NO_PILL_DETECTED`인데 이미지 품질이 정상이고 알약 존재 확인된 케이스
- 분류 데이터셋 편입:
  - `LOW_CONFIDENCE` 또는 `UNKNOWN_PILL`이며 검수로 정답 라벨 확정된 케이스
- 공통:
  - 검수 전 샘플은 재학습에 직접 편입하지 않는다.

## 참고
- 본 문서는 오프라인 검수 큐 생성 기준 문서다.
- 실시간 API 응답 계약(`success/candidates/error_code`)에는 영향을 주지 않는다.
