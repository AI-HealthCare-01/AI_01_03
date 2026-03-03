from fastapi import APIRouter
from ai_worker.vision.detector import predict_boxes

router = APIRouter(prefix="/ai", tags=["AI"])

@router.get("/test-yolo")
def test_yolo():
    result = predict_boxes("bus.jpg", conf_thres=0.5)
    return {"count": len(result), "detections": result}