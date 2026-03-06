"""
RAG Chat API 요청/응답 DTO.

Sprint01 통합 계약서(POST /api/chat) 기준.
"""

from pydantic import BaseModel, Field


# ── 요청 ──────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="사용자 질문")
    medication_id: str | None = Field(
        default=None,
        description="약품 식별자 (Vision/OCR 에서 전달, 예: TYLENOL_500)",
    )


# ── 응답 섹션 ─────────────────────────────────
class AnswerSections(BaseModel):
    summary: str = Field(..., description="약 이름과 핵심 정보 요약")
    dosage: str = Field(..., description="복용법 및 용량 안내")
    precautions: str = Field(..., description="주의사항 및 부작용")
    tips: str = Field(..., description="보관법, 복용 팁 등 추가 안내")


class Citation(BaseModel):
    source: str = Field(..., description="출처 경로 또는 URL")
    title: str = Field(..., description="출처 문서 제목")


# ── 성공 응답 ─────────────────────────────────
class ChatResponse(BaseModel):
    success: bool = True
    answer: str = Field(..., description="전체 답변 텍스트")
    sections: AnswerSections
    tts_segments: list[str] = Field(
        default_factory=list,
        description="TTS 재생용 문장 단위 배열",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="참고 출처 목록",
    )
    disclaimer: str = Field(..., description="의료 면책 조항")


# ── 실패 응답 (임계값 미달 등) ────────────────
class ChatErrorResponse(BaseModel):
    success: bool = False
    error_code: str = Field(..., description="에러 코드 (예: LOW_RAG_CONFIDENCE)")
