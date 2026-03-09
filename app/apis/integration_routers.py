from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.core import config
from app.dtos.integration import (
    ChatFailureResponse,
    ChatRequest,
    ChatSections,
    ChatSuccessResponse,
    MedicationDashboardData,
    MedicationDashboardResponse,
    MedicationHistoryData,
    MedicationHistoryItem,
    MedicationHistoryResponse,
    OCRParsed,
    OCRParseRequest,
    OCRParseResponse,
    VisionCandidate,
    VisionIdentifyRequest,
    VisionIdentifyResponse,
)
from app.models.schedules import MedicationSchedule
from app.services.ocr import OCRService
from app.services.prescription_flow import PrescriptionFlowService
from app.services.vision import VisionService, VisionServiceError

integration_router = APIRouter(prefix="/api", tags=["integration"])

_sentence_splitter = re.compile(r"(?<=[.!?])\s+")
_http_url_regex = re.compile(r"^https?://", re.IGNORECASE)
_non_medication_id_regex = re.compile(r"[^A-Z0-9]+")
_medication_aliases = {
    "타이레놀": "TYLENOL_500",
    "아스피린": "ASPIRIN_100",
    "게보린": "GEBORIN_500",
}


def _normalize_medication_id(value: str) -> str:
    normalized = _non_medication_id_regex.sub("_", value.upper()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        return "UNKNOWN_PILL"
    if "_" not in normalized:
        return f"{normalized}_PILL"
    return normalized


def _load_vision_medication_map() -> dict[str, str]:
    path = (config.VISION_MEDICATION_MAP_PATH or "").strip()
    if not path:
        return {}

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    mapped: dict[str, str] = {}
    for source_label, medication_id in payload.items():
        if not isinstance(source_label, str) or not isinstance(medication_id, str):
            continue
        if not medication_id.strip():
            continue
        key_variants = {
            source_label.strip(),
            source_label.strip().upper(),
            _normalize_medication_id(source_label),
        }
        target = _normalize_medication_id(medication_id)
        for key in key_variants:
            if key:
                mapped[key] = target
    return mapped


def _tts_segments(answer: str) -> list[str]:
    answer = (answer or "").strip()
    if not answer:
        return []
    return [s.strip() for s in _sentence_splitter.split(answer) if s.strip()]


def _is_http_url(value: str) -> bool:
    return bool(_http_url_regex.match(value.strip()))


def _format_time_value(value: object) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M:%S")
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours = (total_seconds // 3600) % 24
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return str(value)


def _to_medication_id(raw_name: str, medication_map: dict[str, str] | None = None) -> str:
    name = raw_name.strip()
    if not name:
        return "UNKNOWN_PILL"

    if medication_map:
        normalized_name = _normalize_medication_id(name)
        mapped = medication_map.get(name) or medication_map.get(name.upper()) or medication_map.get(normalized_name)
        if mapped:
            return _normalize_medication_id(mapped)

    for alias, medication_id in _medication_aliases.items():
        if alias in name:
            return medication_id

    return _normalize_medication_id(name)


@integration_router.post("/vision/identify", response_model=VisionIdentifyResponse)
async def vision_identify(
    request: Request,
    vision_service: Annotated[VisionService, Depends(VisionService)],
    image: Annotated[UploadFile | None, File()] = None,
) -> VisionIdentifyResponse:
    payload = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = await request.json()
    except Exception:
        payload = {}

    req = VisionIdentifyRequest.model_validate(payload)
    if req.mock_error_code:
        return VisionIdentifyResponse(success=False, candidates=[], error_code=req.mock_error_code)

    # E2E 계약 호환: 이미지 없이 JSON 요청이 오면 기존 mock 동작 유지.
    if image is None:
        confidence = 0.93 if req.confidence is None else float(req.confidence)
        if confidence < 0.8:
            return VisionIdentifyResponse(success=False, candidates=[], error_code="LOW_CONFIDENCE")
        medication_id = req.medication_id or "TYLENOL_500"
        return VisionIdentifyResponse(
            success=True,
            candidates=[VisionCandidate(medication_id=medication_id, confidence=confidence)],
            error_code=None,
        )

    image_bytes = await image.read()
    try:
        vision_result = await vision_service.identify(
            image_bytes=image_bytes,
            content_type=image.content_type,
        )
    except VisionServiceError as exc:
        return VisionIdentifyResponse(success=False, candidates=[], error_code=exc.error_code)
    except Exception:
        return VisionIdentifyResponse(success=False, candidates=[], error_code="VISION_INTERNAL_ERROR")

    merged_confidence: dict[str, float] = {}
    medication_map = _load_vision_medication_map()
    for detection in vision_result.detections:
        for candidate in detection.candidates:
            medication_id = _to_medication_id(candidate.drug_name, medication_map)
            existing = merged_confidence.get(medication_id)
            if existing is None or candidate.confidence > existing:
                merged_confidence[medication_id] = candidate.confidence

    sorted_candidates = sorted(merged_confidence.items(), key=lambda item: item[1], reverse=True)
    if not sorted_candidates:
        return VisionIdentifyResponse(success=False, candidates=[], error_code="LOW_CONFIDENCE")

    top_confidence = sorted_candidates[0][1]
    if top_confidence < 0.8:
        return VisionIdentifyResponse(success=False, candidates=[], error_code="LOW_CONFIDENCE")

    top_k = max(1, config.VISION_TOP_K)
    candidates = [
        VisionCandidate(medication_id=medication_id, confidence=confidence)
        for medication_id, confidence in sorted_candidates[:top_k]
    ]
    return VisionIdentifyResponse(success=True, candidates=candidates, error_code=None)


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


@integration_router.get("/history", response_model=MedicationHistoryResponse)
async def medication_history(user_id: Annotated[int, Query(ge=1)]) -> MedicationHistoryResponse:
    schedules = (
        await MedicationSchedule.filter(user_id=user_id)
        .select_related("prescription_item")
        .order_by("-created_at", "-id")
    )

    items = [
        MedicationHistoryItem(
            schedule_id=int(schedule.id),
            medication_name=schedule.prescription_item.name,
            dose_text=schedule.prescription_item.dose_text,
            day_offset=int(schedule.day_offset),
            time_slot=schedule.time_slot,
            scheduled_time=_format_time_value(schedule.scheduled_time),
            is_completed=bool(schedule.is_completed),
        )
        for schedule in schedules
    ]
    completed_count = sum(1 for schedule in schedules if schedule.is_completed)
    total_count = len(schedules)
    data = MedicationHistoryData(
        total_count=total_count,
        completed_count=completed_count,
        pending_count=total_count - completed_count,
        items=items,
    )
    return MedicationHistoryResponse(success=True, error_code=None, data=data)


@integration_router.get("/dashboard", response_model=MedicationDashboardResponse)
async def medication_dashboard(user_id: Annotated[int, Query(ge=1)]) -> MedicationDashboardResponse:
    total_schedules = await MedicationSchedule.filter(user_id=user_id).count()
    completed_schedules = await MedicationSchedule.filter(user_id=user_id, is_completed=True).count()
    upcoming_schedules = total_schedules - completed_schedules
    adherence_rate = round((completed_schedules / total_schedules) * 100, 2) if total_schedules else 0.0

    data = MedicationDashboardData(
        total_schedules=total_schedules,
        completed_schedules=completed_schedules,
        upcoming_schedules=upcoming_schedules,
        adherence_rate=adherence_rate,
    )
    return MedicationDashboardResponse(success=True, error_code=None, data=data)
