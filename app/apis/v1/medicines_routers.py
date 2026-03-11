from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.ocr import OCRService

medicines_router = APIRouter(prefix="/medicines", tags=["Medicines"])

_DOSE_PARSE_REGEX = re.compile(r"(\d+)\s*일\s*(\d+)\s*회\s*,\s*(\d+)\s*일분")


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
    m = _DOSE_PARSE_REGEX.search(dose_text)
    if m:
        freq = m.group(2)
        duration_days = m.group(3)
        return "1정", f"하루 {freq}회", f"{duration_days}일", "식후"
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
