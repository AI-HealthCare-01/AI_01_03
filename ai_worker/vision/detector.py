from ultralytics import YOLO
from ai_worker.core import default_logger

_detector = None  # 모델을 한 번만 로드하기 위한 전역 캐시

def get_detector(model_path: str = "yolov8n.pt"):
    global _detector
    if _detector is None:
        default_logger.info(f"[YOLO] Loading model: {model_path}")
        _detector = YOLO(model_path)
    return _detector

def predict_boxes(image_path: str, conf_thres: float = 0.5, model_path: str = "yolov8n.pt"):
    model = get_detector(model_path)
    results = model(image_path)
    r0 = results[0]
    boxes = r0.boxes

    out = []
    if boxes is None:
        return out

    for b in boxes:
        cls_id = int(b.cls.item())
        conf = float(b.conf.item())
        if conf < conf_thres:
            continue
        x1, y1, x2, y2 = [float(x) for x in b.xyxy[0].tolist()]
        out.append({
            "class_id": cls_id,
            "class_name": model.names.get(cls_id, str(cls_id)),
            "confidence": conf,
            "xyxy": [x1, y1, x2, y2],
        })
    return out