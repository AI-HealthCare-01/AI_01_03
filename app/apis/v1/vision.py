import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile
from PIL import Image

from ai_worker.vision.classifier import get_classifier
from ai_worker.vision.detector import predict_boxes

router = APIRouter(prefix="/vision", tags=["Vision"])

TEMP_DIR = Path("tmp")
CROP_DIR = TEMP_DIR / "crops"
TEMP_DIR.mkdir(exist_ok=True)
CROP_DIR.mkdir(parents=True, exist_ok=True)

THRESHOLD = 0.8
TOPK = 3


def _to_xyxy(det: dict, img_w: int, img_h: int):
    """
    detector 결과 dict에서 bbox를 최대한 유연하게 xyxy로 변환.
    지원 케이스:
    - det["bbox"] = [x, y, w, h] (COCO)
    - det["bbox"] = [x1, y1, x2, y2] (xyxy)
    - det["xyxy"] = [x1, y1, x2, y2]
    """
    if "xyxy" in det and det["xyxy"]:
        x1, y1, x2, y2 = det["xyxy"]
    elif "bbox" in det and det["bbox"]:
        b = det["bbox"]
        if len(b) != 4:
            return None
        x1, y1, a, b2 = b
        # COCO([x,y,w,h])인지 xyxy([x1,y1,x2,y2])인지 추정
        if a <= img_w and b2 <= img_h and (x1 + a) <= img_w and (y1 + b2) <= img_h:
            # [x,y,w,h]
            x2, y2 = x1 + a, y1 + b2
        else:
            # [x1,y1,x2,y2]
            x2, y2 = a, b2
    else:
        return None

    # clamp
    x1 = max(0, min(int(x1), img_w - 1))
    y1 = max(0, min(int(y1), img_h - 1))
    x2 = max(1, min(int(x2), img_w))
    y2 = max(1, min(int(y2), img_h))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


@router.post("/identify")
async def identify(file: UploadFile):
    # 1) 업로드 파일 임시 저장
    img_path = TEMP_DIR / file.filename
    with open(img_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2) YOLO 탐지
    detections = predict_boxes(str(img_path), conf_thres=0.25)  # 필요시 조정
    if not detections:
        return {"success": False, "candidates": [], "error_code": "LOW_CONFIDENCE"}

    # 3) crop + 분류
    classifier = get_classifier()

    with Image.open(img_path) as im:
        im = im.convert("RGB")
        w, h = im.size

        candidates = []
        for i, det in enumerate(detections):
            xyxy = _to_xyxy(det, w, h)
            if xyxy is None:
                continue

            x1, y1, x2, y2 = xyxy
            crop = im.crop((x1, y1, x2, y2))

            crop_path = CROP_DIR / f"{img_path.stem}__{i}.png"
            crop.save(crop_path)

            medication_id, cls_conf = classifier.predict(str(crop_path))

            det_conf = float(det.get("conf", det.get("confidence", 1.0)))
            final_conf = det_conf * float(cls_conf)  # 보수적으로 결합

            candidates.append({"medication_id": medication_id, "confidence": round(final_conf, 4)})

    # 4) 후보 정리 + Sprint01 규칙 적용
    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    candidates = candidates[:TOPK]

    if len(candidates) == 0 or candidates[0]["confidence"] < THRESHOLD:
        return {"success": False, "candidates": [], "error_code": "LOW_CONFIDENCE"}

    return {"success": True, "candidates": candidates, "error_code": None}
