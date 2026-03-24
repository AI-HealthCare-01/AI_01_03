from fastapi import APIRouter, HTTPException, UploadFile

from app.core import default_logger
from app.services.vision import VisionService, VisionServiceError

router = APIRouter(prefix="/vision", tags=["Vision"])

_vision_service = VisionService()


@router.post("/identify")
async def identify(file: UploadFile):
    image_bytes = await file.read()
    try:
        result = await _vision_service.identify(
            image_bytes=image_bytes,
            content_type=file.content_type,
        )
    except VisionServiceError as exc:
        default_logger.warning("[Vision Router] %s: %s", exc.error_code, exc.message)
        if exc.error_code == "NO_PILL_DETECTED":
            return {"success": False, "candidates": [], "error_code": "LOW_CONFIDENCE"}
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    # detections → flat candidates 변환 (기존 API 호환)
    candidates = []
    for det in result.detections:
        for c in det.candidates:
            candidates.append({"medication_id": c.drug_name, "confidence": round(c.confidence, 4)})

    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    candidates = candidates[:3]

    if not candidates or candidates[0]["confidence"] < 0.8:
        return {"success": False, "candidates": [], "error_code": "LOW_CONFIDENCE"}

    return {"success": True, "candidates": candidates, "error_code": None}
