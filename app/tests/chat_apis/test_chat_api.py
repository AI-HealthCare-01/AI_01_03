"""
POST /api/v1/chat API 테스트.

- 정상 응답 구조 검증
- 가드레일 (임계값 미달) 검증
- 출력 포맷 계약 준수 검증
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE_URL = "http://test"
CHAT_URL = "/api/v1/chat"


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url=BASE_URL)


# ── 정상 응답 테스트 ──────────────────────────


@pytest.mark.asyncio
async def test_chat_success_response_structure(client: AsyncClient):
    """성공 응답이 계약서 형식을 준수하는지 검증."""
    response = await client.post(CHAT_URL, json={"question": "타이레놀 복용법 알려줘"})
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0

    # sections 4개 필드 존재
    sections = data["sections"]
    for key in ("summary", "dosage", "precautions", "tips"):
        assert key in sections
        assert isinstance(sections[key], str)

    # tts_segments 배열
    assert isinstance(data["tts_segments"], list)
    assert len(data["tts_segments"]) > 0

    # citations 배열 및 필수 필드
    assert isinstance(data["citations"], list)
    for citation in data["citations"]:
        assert "source" in citation
        assert "title" in citation

    # disclaimer 항상 포함
    assert isinstance(data["disclaimer"], str)
    assert len(data["disclaimer"]) > 0


@pytest.mark.asyncio
async def test_chat_disclaimer_always_present(client: AsyncClient):
    """면책 조항이 항상 포함되는지 검증."""
    response = await client.post(CHAT_URL, json={"question": "아세트아미노펜 부작용"})
    data = response.json()
    assert "의학적 진단이나 처방을 대체하지 않습니다" in data["disclaimer"]


# ── 입력 검증 테스트 ──────────────────────────


@pytest.mark.asyncio
async def test_chat_empty_question_rejected(client: AsyncClient):
    """빈 질문은 422 에러를 반환해야 함."""
    response = await client.post(CHAT_URL, json={"question": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_missing_question_rejected(client: AsyncClient):
    """question 필드 누락 시 422 에러를 반환해야 함."""
    response = await client.post(CHAT_URL, json={})
    assert response.status_code == 422


# ── 서비스 단위 테스트 ────────────────────────


class TestLLMGuideService:
    """LLMGuideService 가드레일 로직 단위 테스트."""

    def setup_method(self):
        from app.services.llm_guide import LLMGuideService

        self.service = LLMGuideService(confidence_threshold=0.45)

    def test_confidence_pass(self):
        """임계값 이상 → 답변 생성 허용."""
        assert self.service.check_rag_confidence([0.60, 0.75]) is True

    def test_confidence_fail(self):
        """임계값 미달 → 답변 생성 차단."""
        assert self.service.check_rag_confidence([0.10, 0.30]) is False

    def test_confidence_empty_scores(self):
        """검색 결과 없음 → 안전 응답."""
        assert self.service.check_rag_confidence([]) is False

    def test_confidence_boundary(self):
        """임계값 경계값(0.45) → 통과."""
        assert self.service.check_rag_confidence([0.45]) is True

    def test_safe_response_structure(self):
        """안전 응답 구조 검증."""
        resp = self.service.build_safe_response()
        assert resp["success"] is False
        assert resp["error_code"] == "LOW_RAG_CONFIDENCE"

    def test_parse_sections_from_raw(self):
        """LLM 원문에서 섹션 파싱 검증."""
        raw = (
            "summary: 타이레놀은 해열진통제입니다.\n"
            "dosage: 1회 1정, 1일 3회.\n"
            "precautions: 간 질환자 주의.\n"
            "tips: 서늘한 곳 보관."
        )
        sections = self.service.parse_sections(raw)
        assert "해열진통제" in sections["summary"]
        assert "1정" in sections["dosage"]
        assert "간 질환" in sections["precautions"]
        assert "보관" in sections["tips"]

    def test_tts_segments_split(self):
        """TTS 세그먼트 분할 검증."""
        text = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째!"
        segments = self.service.split_tts_segments(text)
        assert len(segments) == 3

    def test_out_of_scope_marker_detected(self):
        """안전 응답 문구 감지 검증."""
        from app.prompts.system_prompt import SAFE_FALLBACK_ANSWER

        assert self.service.contains_out_of_scope_marker(SAFE_FALLBACK_ANSWER) is True
        assert self.service.contains_out_of_scope_marker("일반 답변입니다.") is False


# ── 프롬프트 빌드 테스트 ──────────────────────


class TestSystemPrompt:
    """시스템 프롬프트 구성 테스트."""

    def test_build_system_prompt_has_required_sections(self):
        from app.prompts.system_prompt import build_system_prompt

        prompt = build_system_prompt()
        assert "컨텍스트 기반 답변만 허용" in prompt
        assert "의료 면책" in prompt
        assert "{{context}}" in prompt
        assert "{{question}}" in prompt

    def test_build_chat_prompt_replaces_placeholders(self):
        from app.prompts.system_prompt import build_chat_prompt

        result = build_chat_prompt(context="테스트 컨텍스트", question="테스트 질문")
        assert "테스트 컨텍스트" in result
        assert "테스트 질문" in result
        assert "{{context}}" not in result
        assert "{{question}}" not in result
