from __future__ import annotations

import base64
import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.ocr import OCRService
from app.services.tts import generate_tts
from app.services.vision import VisionService, VisionServiceError

medicines_router = APIRouter(prefix="/medicines", tags=["Medicines"])

# 형식 1: 1정씩3회3일분 / 1캡슐씩3회3일분
_DOSE_PARSE_NEW = re.compile(r"(\d+[가-힣]*)\s*씩\s*(\d+)\s*회\s*(\d+)\s*일분")
# 형식 2: 3일 2회, 3일분
_DOSE_PARSE_OLD = re.compile(r"(\d+)\s*일\s*(\d+)\s*회\s*,\s*(\d+)\s*일분")


class PrescriptionOcrItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    schedule: str


class PrescriptionOcrResponse(BaseModel):
    items: list[PrescriptionOcrItem]


def _parse_dose_text(dose_text: str) -> tuple[str, str, str, str]:
    """dose_text 파싱 → (dosage, frequency, duration, schedule)"""
    # 형식 1: 1정씩3회3일분
    m = _DOSE_PARSE_NEW.search(dose_text)
    if m:
        dosage = m.group(1)   # "1정" or "1캡슐"
        freq = m.group(2)     # "3"
        duration = m.group(3) # "3"
        return dosage, f"하루 {freq}회", f"{duration}일", "식후"
    # 형식 2: 3일 2회, 3일분
    m = _DOSE_PARSE_OLD.search(dose_text)
    if m:
        freq = m.group(2)
        duration = m.group(3)
        return "1정", f"하루 {freq}회", f"{duration}일", "식후"
    return "1정", dose_text, "", "식후"


@medicines_router.post("/ocr/prescription", response_model=PrescriptionOcrResponse)
async def ocr_prescription(
    ocr_service: Annotated[OCRService, Depends(OCRService)],
    image: UploadFile = File(...),
) -> PrescriptionOcrResponse:
    image_bytes = await image.read()
    content_type = image.content_type or "image/jpeg"
    fmt = content_type.split("/")[-1].lower() if "/" in content_type else "jpg"

    try:
        text = await ocr_service.extract_text_from_image_bytes(image_bytes, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="OCR processing failed") from exc

    medications = ocr_service.parse_prescription_text(text)

    items = []
    for med in medications:
        dosage, frequency, duration, schedule = _parse_dose_text(med.dose_text)
        items.append(
            PrescriptionOcrItem(
                name=med.name,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                schedule=schedule,
            )
        )

    return PrescriptionOcrResponse(items=items)


# ── TTS ──────────────────────────────────────────────────────────────────────

class MedicineTTSRequest(BaseModel):
    guide_id: str = ""
    text: str = ""
    lang: str = "ko"


class MedicineTTSResponse(BaseModel):
    audio_url: str


@medicines_router.post("/tts", response_model=MedicineTTSResponse)
async def medicines_tts(request: MedicineTTSRequest) -> MedicineTTSResponse:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    try:
        audio_fp = await generate_tts(text=request.text, lang=request.lang)
        audio_bytes = audio_fp.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="TTS 생성 실패") from exc

    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return MedicineTTSResponse(audio_url=f"data:audio/mpeg;base64,{b64}")


# ── 알약 인식 ──────────────────────────────────────────────────────────────────

class MedicineRecognizeResponse(BaseModel):
    medicine_name: str


@medicines_router.post("/recognize", response_model=MedicineRecognizeResponse)
async def recognize_pill(
    vision_service: Annotated[VisionService, Depends(VisionService)],
    image: UploadFile = File(...),
) -> MedicineRecognizeResponse:
    image_bytes = await image.read()

    try:
        result = await vision_service.identify(
            image_bytes=image_bytes,
            content_type=image.content_type,
        )
    except VisionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="알약 인식 실패") from exc

    medicine_name = "식별불가"
    for detection in result.detections:
        if detection.candidates:
            medicine_name = detection.candidates[0].drug_name
            break

    return MedicineRecognizeResponse(medicine_name=medicine_name)
