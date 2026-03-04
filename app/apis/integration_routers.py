from __future__ import annotations

import re

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.dtos.integration import (
    ChatFailureResponse,
    ChatRequest,
    ChatSections,
    ChatSuccessResponse,
    OCRParseRequest,
    OCRParseResponse,
    OCRParsed,
    VisionCandidate,
    VisionIdentifyRequest,
    VisionIdentifyResponse,
)
from app.services.ocr import OCRService
from app.services.prescription_flow import PrescriptionFlowService

integration_router = APIRouter(prefix="/api", tags=["integration"])

_sentence_splitter = re.compile(r"(?<=[.!?])\s+")
_http_url_regex = re.compile(r"^https?://", re.IGNORECASE)


def _tts_segments(answer: str) -> list[str]:
    answer = (answer or "").strip()
    if not answer:
        return []
    return [s.strip() for s in _sentence_splitter.split(answer) if s.strip()]


def _is_http_url(value: str) -> bool:
    return bool(_http_url_regex.match(value.strip()))


@integration_router.post("/vision/identify", response_model=VisionIdentifyResponse)
async def vision_identify(request: Request) -> VisionIdentifyResponse:
    payload = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = await request.json()
    except Exception:
        payload = {}

    req = VisionIdentifyRequest.model_validate(payload)

    if req.mock_error_code:
        return VisionIdentifyResponse(success=False, candidates=[], error_code=req.mock_error_code)

    confidence = 0.93 if req.confidence is None else float(req.confidence)
    if confidence < 0.8:
        return VisionIdentifyResponse(success=False, candidates=[], error_code="LOW_CONFIDENCE")

    medication_id = req.medication_id or "TYLENOL_500"
    candidate = VisionCandidate(medication_id=medication_id, confidence=confidence)
    return VisionIdentifyResponse(success=True, candidates=[candidate], error_code=None)


@integration_router.post("/ocr/parse", response_model=OCRParseResponse)
async def ocr_parse(
    request: Request,
    ocr_service: Annotated[OCRService, Depends(OCRService)],
    prescription_flow_service: Annotated[PrescriptionFlowService, Depends(PrescriptionFlowService)],
) -> OCRParseResponse:
    payload = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = await request.json()
    except Exception:
        payload = {}

    req = OCRParseRequest.model_validate(payload)

    if req.mock_error_code:
        return OCRParseResponse(success=False, parsed=None, error_code=req.mock_error_code)

    text = (req.text or "").strip()
    image_url = (req.image_url or "").strip()

    # UI 합의 규격: text 또는 image_url 중 최소 1개는 필요하며, image_url은 http/https만 허용.
    if not text and not image_url:
        return OCRParseResponse(success=False, parsed=None, error_code="PARSE_FAILED")

    if image_url and not _is_http_url(image_url):
        return OCRParseResponse(success=False, parsed=None, error_code="PARSE_FAILED")

    # 둘 다 전달되면 text 우선 사용(네트워크 OCR 호출 회피).
    if not text and image_url:
        try:
            text = await ocr_service.extract_text_from_image_url(image_url)
        except Exception:
            return OCRParseResponse(success=False, parsed=None, error_code="PARSE_FAILED")

    medications = ocr_service.parse_prescription_text(text)
    if not medications:
        return OCRParseResponse(success=False, parsed=None, error_code="PARSE_FAILED")

    if req.save_to_db:
        if req.user_id is None:
            return OCRParseResponse(success=False, parsed=None, error_code="OCR_DB_SAVE_FAILED")
        try:
            await prescription_flow_service.save_prescription_with_schedules(
                user_id=req.user_id,
                source_text=text,
                medications=medications,
            )
        except Exception:
            return OCRParseResponse(success=False, parsed=None, error_code="OCR_DB_SAVE_FAILED")

    parsed = OCRParsed(medications=medications)
    return OCRParseResponse(success=True, parsed=parsed, error_code=None)


@integration_router.post("/chat", response_model=ChatSuccessResponse | ChatFailureResponse)
async def chat(request: Request) -> ChatSuccessResponse | ChatFailureResponse:
    payload = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = await request.json()
    except Exception:
        payload = {}

    req = ChatRequest.model_validate(payload)

    if req.mock_error_code:
        return ChatFailureResponse(success=False, error_code=req.mock_error_code)

    rag_confidence = 1.0 if req.rag_confidence is None else float(req.rag_confidence)
    if rag_confidence < 0.5:
        return ChatFailureResponse(success=False, error_code="LOW_RAG_CONFIDENCE")

    medication_id = req.medication_id or "TYLENOL_500"
    question = (req.user_question or "").strip() or "복용 방법과 주의사항을 알려줘."

    answer = f"{medication_id}에 대한 안내입니다. 질문: {question}"
    sections = ChatSections(
        summary=f"{medication_id} 요약 정보입니다.",
        dosage="의사/약사 안내에 따라 복용하세요.",
        precautions="이상 반응이 있으면 복용을 중단하고 전문가와 상담하세요.",
        tips="복용 시간을 기록해두면 도움이 됩니다.",
    )
    disclaimer = "본 답변은 참고용이며, 의료 전문가의 진료/상담을 대체할 수 없습니다."

    return ChatSuccessResponse(
        success=True,
        error_code=None,
        answer=answer,
        sections=sections,
        tts_segments=_tts_segments(answer),
        citations=[],
        disclaimer=disclaimer,
    )
