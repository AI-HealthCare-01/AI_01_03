"""
POST /api/chat — RAG 기반 의약품 안내 API.

Sprint01 통합 계약서 섹션 4 기준.
LLM: GPT-4o-mini
"""

import logging

from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from app.dtos.chat import ChatErrorResponse, ChatRequest, ChatResponse
from app.services.live_drug_lookup import lookup_drug_async
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

    # ── Step 2: 가드레일 — 임계값 검증 + 실시간 조회 fallback ──
    logger.warning("RAG scores: %s (threshold=%.2f)", rag_scores, _llm_service.confidence_threshold)
    if not _llm_service.check_rag_confidence(rag_scores):
        logger.info("RAG 임계값 미달 — 실시간 API 조회 시도: %s", question)
        live_result = await lookup_drug_async(question)
        if live_result:
            live_context, live_name = live_result
            rag_context = live_context
            rag_citations = [{"source": "식약처 실시간 조회", "title": live_name}]
            logger.info("실시간 조회 성공: %s", live_name)
        else:
            logger.warning("실시간 조회도 실패 — GPT 일반 지식 답변 시도")
            rag_context = ""
            rag_citations = []

    # ── Step 3: LLM 답변 생성 ──
    try:
        if rag_context:
            raw_answer = await _llm_service.generate_answer(
                context=rag_context,
                question=question,
            )
        else:
            # 컨텍스트 없으면 거절 문구 없는 일반 지식 프롬프트 사용
            raw_answer = await _llm_service.generate_answer_general(question=question)
    except Exception:
        logger.exception("LLM 호출 실패")
        return ORJSONResponse(
            content={"success": False, "error_code": "LLM_CALL_FAILED"},
            status_code=500,
        )

    # ── Step 4: 안전 응답 감지 ──
    logger.warning("LLM 응답 preview: %s", raw_answer[:200])
    if _llm_service.contains_out_of_scope_marker(raw_answer):
        logger.warning("LLM이 컨텍스트 외 질문으로 판단 — 실시간 조회 재시도")
        live_result = await lookup_drug_async(question)
        if live_result:
            live_context, live_name = live_result
            logger.info("실시간 조회 성공 (LLM fallback): %s", live_name)
            try:
                raw_answer = await _llm_service.generate_answer(
                    context=live_context,
                    question=question,
                )
            except Exception:
                logger.exception("LLM 재호출 실패")
                return ORJSONResponse(
                    content={"success": False, "error_code": "LLM_CALL_FAILED"},
                    status_code=500,
                )
            rag_citations = [{"source": "식약처 실시간 조회", "title": live_name}]

        # 여전히 안전 응답이면 → 거절 문구 없는 일반 지식 프롬프트로 최종 시도
        if _llm_service.contains_out_of_scope_marker(raw_answer):
            logger.warning("최종 fallback — GPT 일반 지식 답변 시도 (거절 문구 없는 프롬프트)")
            rag_citations = [{"source": "일반 의약품 지식", "title": "GPT 일반 답변"}]
            try:
                raw_answer = await _llm_service.generate_answer_general(question=question)
            except Exception:
                logger.exception("GPT 일반 지식 답변 실패")

    # ── Step 5: 응답 조립 ──
    response_data = _llm_service.build_success_response(
        raw_answer=raw_answer,
        citations=rag_citations,
    )

    return ORJSONResponse(content=response_data)
