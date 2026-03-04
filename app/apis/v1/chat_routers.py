"""
POST /api/chat — RAG 기반 의약품 안내 API.

Sprint01 통합 계약서 섹션 4 기준.
LLM: GLM-5 (백엔드 reasoning) via Kilo AI
"""

import logging

from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from app.dtos.chat import ChatErrorResponse, ChatRequest, ChatResponse
from app.services.llm_guide import LLMGuideService
from app.services.rag_search import RAGSearchService

logger = logging.getLogger("chat_router")

chat_router = APIRouter(tags=["Chat"])

_llm_service = LLMGuideService()


@chat_router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        200: {"model": ChatResponse, "description": "의약품 안내 성공"},
        422: {"model": ChatErrorResponse, "description": "RAG 신뢰도 미달"},
    },
    summary="의약품 안내 챗봇",
    description="질문을 받아 RAG 검색 + LLM 생성으로 의약품 정보를 안내합니다.",
)
async def chat(request: ChatRequest) -> ORJSONResponse:
    """RAG → LLM 파이프라인을 실행하고 구조화된 응답을 반환합니다."""
    question = request.question
    medication_id = request.medication_id
    logger.info("Chat 요청 수신: question=%s, medication_id=%s", question, medication_id)

    # ── Step 1: FAISS 검색 ──
    rag = RAGSearchService.get_instance()
    results = rag.search(question, top_k=3)

    rag_scores = [r.score for r in results] if results else []
    rag_context = "\n\n".join(r.chunk for r in results) if results else ""
    rag_citations = [{"source": r.source, "title": r.name} for r in results] if results else []

    # ── Step 2: 가드레일 — 임계값 검증 ──
    if not _llm_service.check_rag_confidence(rag_scores):
        logger.warning("RAG 임계값 미달 — 안전 응답 반환")
        error = _llm_service.build_safe_response()
        return ORJSONResponse(content=error, status_code=422)

    # ── Step 3: GLM-5 답변 생성 ──
    try:
        raw_answer = await _llm_service.generate_answer(
            context=rag_context,
            question=question,
        )
    except Exception:
        logger.exception("LLM 호출 실패")
        return ORJSONResponse(
            content={"success": False, "error_code": "LLM_CALL_FAILED"},
            status_code=500,
        )

    # ── Step 4: 안전 응답 감지 ──
    if _llm_service.contains_out_of_scope_marker(raw_answer):
        logger.info("LLM이 컨텍스트 외 질문으로 판단 — 안전 응답 반환")
        error = _llm_service.build_safe_response()
        return ORJSONResponse(content=error, status_code=422)

    # ── Step 5: 응답 조립 ──
    response_data = _llm_service.build_success_response(
        raw_answer=raw_answer,
        citations=rag_citations,
    )

    return ORJSONResponse(content=response_data)
