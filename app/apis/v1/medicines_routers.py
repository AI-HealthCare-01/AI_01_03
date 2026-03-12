from __future__ import annotations

import base64
import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core import config
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


async def _parse_with_gpt(text: str) -> list[PrescriptionOcrItem]:
    """GPT-4o-mini로 OCR 텍스트에서 약품 정보 추출 (regex 실패 시 fallback)."""
    if not config.OPENAI_API_KEY:
        return []
    try:
        import json as _json
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=800,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 처방전 OCR 텍스트에서 약품 정보를 추출하는 어시스턴트다. "
                        "반드시 JSON object만 반환하라. "
                        "형식: {\"items\": [{\"name\": \"약품명\", \"dosage\": \"1정\", "
                        "\"frequency\": \"하루 3회\", \"duration\": \"3일\", \"schedule\": \"식후\"}]}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"다음 처방전 OCR 텍스트에서 약품명, 1회 투약량, 복용 횟수, 복용 기간, 복용 시간을 추출해줘.\n\n{text}"
                    ),
                },
            ],
        )
        content = completion.choices[0].message.content or ""
        parsed = _json.loads(content)
        raw_items = parsed.get("items", [])
        return [
            PrescriptionOcrItem(
                name=item.get("name", "확인필요"),
                dosage=item.get("dosage", "1정"),
                frequency=item.get("frequency", ""),
                duration=item.get("duration", ""),
                schedule=item.get("schedule", "식후"),
            )
            for item in raw_items
            if item.get("name")
        ]
    except Exception:
        return []


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

    # 1차: regex 파싱
    medications = ocr_service.parse_prescription_text(text)
    items = []
    for med in medications:
        dosage, frequency, duration, schedule = _parse_dose_text(med.dose_text)
        items.append(PrescriptionOcrItem(
            name=med.name, dosage=dosage,
            frequency=frequency, duration=duration, schedule=schedule,
        ))

    # 2차: regex 결과 없으면 GPT fallback
    if not items:
        items = await _parse_with_gpt(text)

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


# ── 약품 정보 조회 ─────────────────────────────────────────────────────────────


class MedicineInfoRequest(BaseModel):
    name: str


class MedicineInfoResponse(BaseModel):
    summary: str
    dosage: str
    precautions: str


@medicines_router.post("/info", response_model=MedicineInfoResponse)
async def get_medicine_info(request: MedicineInfoRequest) -> MedicineInfoResponse:
    """GPT-4o-mini로 약품/영양제 정보 조회."""
    if not config.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    try:
        import json as _json
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=600,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 약품/영양제 정보를 안내하는 어시스턴트다. "
                        "반드시 JSON object만 반환하라. "
                        '형식: {"summary": "효능 요약", "dosage": "복용법", "precautions": "주의사항"}'
                    ),
                },
                {
                    "role": "user",
                    "content": f"{request.name}의 효능, 복용법, 주의사항을 한국어로 간략히 알려줘.",
                },
            ],
        )
        content = completion.choices[0].message.content or "{}"
        data = _json.loads(content)
        return MedicineInfoResponse(
            summary=data.get("summary", ""),
            dosage=data.get("dosage", ""),
            precautions=data.get("precautions", ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="약품 정보 조회 실패") from exc


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
