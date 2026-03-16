from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.core import config, default_logger
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
    VisionDetailRequest,
    VisionDetailResponse,
    VisionIdentifyRequest,
    VisionIdentifyResponse,
)
from app.models.drug_reference import DrugReference
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


def _best_effort_drug_query(*, medication_id: str, drug_name_hint: str | None = None) -> str:
    hint = (drug_name_hint or "").strip()
    if hint:
        return hint

    normalized_medication_id = _normalize_medication_id(medication_id)
    if not normalized_medication_id:
        return ""

    # alias reverse lookup (ex: TYLENOL_500 -> 타이레놀)
    for alias_name, alias_medication_id in _medication_aliases.items():
        if _normalize_medication_id(alias_medication_id) == normalized_medication_id:
            return alias_name

    # vision medication map reverse lookup (target medication_id -> source label)
    path = (config.VISION_MEDICATION_MAP_PATH or "").strip()
    if path:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                for source_label, target_medication_id in payload.items():
                    if not isinstance(source_label, str) or not isinstance(target_medication_id, str):
                        continue
                    if _normalize_medication_id(target_medication_id) == normalized_medication_id:
                        source = source_label.strip()
                        if source:
                            return source
        except Exception:
            pass

    # fallback: keep class-like token readable for search
    if normalized_medication_id.startswith("K_"):
        return normalized_medication_id.replace("_", "-", 1)
    return normalized_medication_id.replace("_", " ")


def _build_drug_reference_context(drug: DrugReference) -> str | None:
    lines: list[str] = []

    title_parts = [part for part in [drug.drug_name, drug.company_name] if part]
    if title_parts:
        if len(title_parts) == 2:
            lines.append(f"[약품명] {title_parts[0]} — {title_parts[1]}")
        else:
            lines.append(f"[약품명] {title_parts[0]}")

    field_map = [
        ("효능/효과", drug.efficacy_text),
        ("용법/용량", drug.dosage_text),
        ("주의사항", drug.precautions_text),
        ("경고", drug.warnings_text),
        ("상호작용", drug.interactions_text),
        ("부작용", drug.side_effects_text),
        ("보관법", drug.storage_text),
    ]

    for label, value in field_map:
        text = (value or "").strip()
        if text:
            lines.append(f"[{label}] {text}")

    if not lines:
        return None
    return "\n".join(lines)


def _build_vision_sample_record(
    *,
    sample_id: str,
    created_at: str,
    request_endpoint: str,
    source_type: str,
    original_image_path: str | None,
    content_type: str | None,
    image_size_bytes: int,
    success: bool,
    error_code: str | None,
    predicted_candidates: list[dict[str, object]],
    detection_boxes: list[list[int]],
    raw_detections: list[dict[str, object]] | None,
    model_version_detect: str,
    model_version_classify: str,
) -> dict[str, object]:
    top1_medication_id: str | None = None
    top1_confidence = 0.0
    if predicted_candidates:
        top1 = predicted_candidates[0]
        top1_medication_id = str(top1.get("medication_id", "")).strip() or None
        try:
            top1_confidence = float(top1.get("confidence", 0.0))
        except Exception:
            top1_confidence = 0.0

    return {
        "sample_id": sample_id,
        "created_at": created_at,
        "request_endpoint": request_endpoint,
        "source_type": source_type,
        "original_image_path": original_image_path,
        "content_type": content_type,
        "image_size_bytes": image_size_bytes,
        "success": success,
        "error_code": error_code,
        "predicted_candidates": predicted_candidates,
        "top1_medication_id": top1_medication_id,
        "top1_confidence": round(top1_confidence, 4),
        "detection_boxes": detection_boxes,
        "raw_detections": raw_detections or [],
        "model_version_detect": model_version_detect,
        "model_version_classify": model_version_classify,
    }


def _persist_vision_sample(
    *,
    image_bytes: bytes | None,
    content_type: str | None,
    request_endpoint: str,
    success: bool,
    error_code: str | None,
    predicted_candidates: list[dict[str, object]],
    detection_boxes: list[list[int]],
    raw_detections: list[dict[str, object]] | None,
    model_version_detect: str,
    model_version_classify: str,
) -> None:
    if not config.VISION_SAMPLE_LOG_ENABLED:
        return

    try:
        sample_id = uuid4().hex
        created_at = datetime.now(UTC).isoformat()
        root = Path(config.VISION_SAMPLE_ROOT).expanduser()
        images_dir = root / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        ext = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get((content_type or "").lower(), ".bin")
        image_path = images_dir / f"{sample_id}{ext}"
        if image_bytes:
            image_path.write_bytes(image_bytes)

        record = _build_vision_sample_record(
            sample_id=sample_id,
            created_at=created_at,
            request_endpoint=request_endpoint,
            source_type="user_upload",
            original_image_path=str(image_path),
            content_type=content_type,
            image_size_bytes=len(image_bytes or b""),
            success=success,
            error_code=error_code,
            predicted_candidates=predicted_candidates,
            detection_boxes=detection_boxes,
            raw_detections=raw_detections,
            model_version_detect=model_version_detect,
            model_version_classify=model_version_classify,
        )

        records_path = root / "records.jsonl"
        with records_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        default_logger.warning("[VisionSample] failed to persist sample: %s", exc)


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
    request_endpoint = "/api/vision/identify"
    try:
        vision_result = await vision_service.identify(
            image_bytes=image_bytes,
            content_type=image.content_type,
        )
    except VisionServiceError as exc:
        if exc.error_code == "NO_PILL_DETECTED":
            _persist_vision_sample(
                image_bytes=image_bytes,
                content_type=image.content_type,
                request_endpoint=request_endpoint,
                success=False,
                error_code=exc.error_code,
                predicted_candidates=[],
                detection_boxes=[],
                raw_detections=None,
                model_version_detect=config.VISION_DETECT_MODEL_PATH,
                model_version_classify=config.VISION_CLASSIFIER_MODEL_PATH,
            )
        return VisionIdentifyResponse(success=False, candidates=[], error_code=exc.error_code)
    except Exception:
        _persist_vision_sample(
            image_bytes=image_bytes,
            content_type=image.content_type,
            request_endpoint=request_endpoint,
            success=False,
            error_code="VISION_INTERNAL_ERROR",
            predicted_candidates=[],
            detection_boxes=[],
            raw_detections=None,
            model_version_detect=config.VISION_DETECT_MODEL_PATH,
            model_version_classify=config.VISION_CLASSIFIER_MODEL_PATH,
        )
        return VisionIdentifyResponse(success=False, candidates=[], error_code="VISION_INTERNAL_ERROR")

    merged_confidence: dict[str, float] = {}
    medication_map = _load_vision_medication_map()
    detection_boxes = [detection.bbox for detection in vision_result.detections]
    raw_detections = [
        {
            "bbox": detection.bbox,
            "candidates": [
                {"drug_name": candidate.drug_name, "confidence": candidate.confidence}
                for candidate in detection.candidates
            ],
        }
        for detection in vision_result.detections
    ]
    for detection in vision_result.detections:
        for candidate in detection.candidates:
            medication_id = _to_medication_id(candidate.drug_name, medication_map)
            existing = merged_confidence.get(medication_id)
            if existing is None or candidate.confidence > existing:
                merged_confidence[medication_id] = candidate.confidence

    sorted_candidates = sorted(merged_confidence.items(), key=lambda item: item[1], reverse=True)
    if not sorted_candidates:
        _persist_vision_sample(
            image_bytes=image_bytes,
            content_type=image.content_type,
            request_endpoint=request_endpoint,
            success=False,
            error_code="LOW_CONFIDENCE",
            predicted_candidates=[],
            detection_boxes=detection_boxes,
            raw_detections=raw_detections,
            model_version_detect=config.VISION_DETECT_MODEL_PATH,
            model_version_classify=config.VISION_CLASSIFIER_MODEL_PATH,
        )
        return VisionIdentifyResponse(success=False, candidates=[], error_code="LOW_CONFIDENCE")

    top_confidence = sorted_candidates[0][1]
    if top_confidence < 0.8:
        _persist_vision_sample(
            image_bytes=image_bytes,
            content_type=image.content_type,
            request_endpoint=request_endpoint,
            success=False,
            error_code="LOW_CONFIDENCE",
            predicted_candidates=[],
            detection_boxes=detection_boxes,
            raw_detections=raw_detections,
            model_version_detect=config.VISION_DETECT_MODEL_PATH,
            model_version_classify=config.VISION_CLASSIFIER_MODEL_PATH,
        )
        return VisionIdentifyResponse(success=False, candidates=[], error_code="LOW_CONFIDENCE")

    top_k = max(1, config.VISION_TOP_K)
    candidates = [
        VisionCandidate(medication_id=medication_id, confidence=confidence)
        for medication_id, confidence in sorted_candidates[:top_k]
    ]
    persisted_candidates = [
        {"medication_id": candidate.medication_id, "confidence": candidate.confidence} for candidate in candidates
    ]
    _persist_vision_sample(
        image_bytes=image_bytes,
        content_type=image.content_type,
        request_endpoint=request_endpoint,
        success=True,
        error_code=None,
        predicted_candidates=persisted_candidates,
        detection_boxes=detection_boxes,
        raw_detections=raw_detections,
        model_version_detect=config.VISION_DETECT_MODEL_PATH,
        model_version_classify=config.VISION_CLASSIFIER_MODEL_PATH,
    )
    return VisionIdentifyResponse(success=True, candidates=candidates, error_code=None)


@integration_router.post("/vision/detail", response_model=VisionDetailResponse)
async def vision_detail(request: VisionDetailRequest) -> VisionDetailResponse:
    medication_id = request.medication_id
    drug = await DrugReference.get_or_none(medication_id=medication_id)

    hint = (request.drug_name_hint or "").strip()
    if drug is None and hint:
        drug = await DrugReference.filter(drug_name__icontains=hint).order_by("-updated_at").first()

    if drug is None:
        return VisionDetailResponse(
            success=False,
            error_code="DRUG_INFO_NOT_FOUND",
            medication_id=medication_id,
            drug_name=None,
            context_text=None,
        )

    context_text = _build_drug_reference_context(drug)
    return VisionDetailResponse(
        success=True,
        error_code=None,
        medication_id=medication_id,
        drug_name=drug.drug_name,
        context_text=context_text,
    )


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
