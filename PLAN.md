# 구현 계획: 03/02~03/03 작업

## 개요
Excel 약품 목록 + 식약처 e약은요 API를 병행하여 RAG용 지식 JSON을 생성한다.
기존 코드 골격(system_prompt.py, llm_guide.py, chat_routers.py, chat.py) 위에 이어서 개발.

---

## Task 1: 식약처 API 파싱 스크립트 작성
**파일:** `scripts/fetch_drug_info.py`

- Excel에서 약품명 5,000건 추출
- e약은요 API(`getDrbEasyDrugList`)로 상세 정보 수집
  - endpoint: `https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList`
  - 파라미터: `serviceKey`, `itemName`, `type=json`, `numOfRows=5`
- 응답 필드 수집: `efcyQesitm`(효능), `useMethodQesitm`(용법), `atpnQesitm`(주의사항), `seQesitm`(부작용), `depositMethodQesitm`(보관법)
- 실패/누락 건수 로깅, 중간 저장(체크포인트) 지원
- API rate limit 대응 (sleep 간격)

## Task 2: 지식 JSON 생성
**파일:** `data/knowledge_base.json`

- 스크립트 결과물을 RAG에 적합한 구조로 변환
- JSON 구조:
```json
{
  "medications": [
    {
      "medication_id": "GERUSAM_200T",
      "name": "게루삼정 200T",
      "category": "일반의약품",
      "c_code": "K-000059",
      "efficacy": "...",
      "dosage": "...",
      "precautions": "...",
      "side_effects": "...",
      "storage": "...",
      "source": "식약처 의약품안전나라"
    }
  ]
}
```
- medication_id는 계약서 규격(영문대문자+언더스코어) 준수

## Task 3: config.py 연동
- DATA_GO_KR_API_KEY_ENCODED/DECODED 이미 추가됨 ✅

## Task 4: 데이터 라이선스 리스크 기록
- 공공데이터 이용 조건 확인 및 문서화

---

## 실행 순서
1. API 연결 테스트 (1건)
2. 파싱 스크립트 작성
3. 전체 수집 실행 → knowledge_base.json 생성
4. 라이선스 리스크 기록
