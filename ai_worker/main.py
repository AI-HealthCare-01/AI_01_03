"""
AI Worker — Redis 큐 기반 비동기 태스크 워커.

FastAPI 앱에서 Redis에 태스크를 넣으면, 이 워커가 꺼내서 처리합니다.
현재 지원 태스크: vision_detect, vision_classify, ping
"""

from __future__ import annotations

import json
import signal
import sys
import time

import redis

from ai_worker.core import default_logger

REDIS_URL = "redis://redis:6379/0"
TASK_QUEUE = "ai:tasks"
RESULT_PREFIX = "ai:result:"

_running = True


def _signal_handler(sig, frame):
    global _running
    default_logger.info("Shutdown signal received, stopping worker...")
    _running = False


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


def handle_task(task: dict) -> dict:
    """태스크 타입에 따라 처리를 분기합니다."""
    task_type = task.get("type", "")
    task_id = task.get("task_id", "unknown")

    default_logger.info("[Task %s] type=%s", task_id, task_type)

    if task_type == "vision_detect":
        from ai_worker.vision.detector import predict_boxes

        image_path = task.get("image_path", "")
        conf = task.get("conf_thres", 0.5)
        model_path = task.get("model_path", "yolov8n.pt")
        boxes = predict_boxes(image_path, conf_thres=conf, model_path=model_path)
        return {"status": "ok", "task_id": task_id, "boxes": boxes}

    elif task_type == "vision_classify":
        from PIL import Image

        from ai_worker.vision.classifier import predict_classes

        image_path = task.get("image_path", "")
        model_path = task.get("model_path", "")
        labels_path = task.get("labels_path")
        top_k = task.get("top_k", 3)
        image = Image.open(image_path)
        predictions = predict_classes(
            image=image,
            model_path=model_path,
            labels_path=labels_path,
            top_k=top_k,
        )
        return {"status": "ok", "task_id": task_id, "predictions": predictions}

    elif task_type == "ping":
        return {"status": "ok", "task_id": task_id, "message": "pong"}

    else:
        return {"status": "error", "task_id": task_id, "message": f"Unknown task type: {task_type}"}


def main():
    default_logger.info("AI Worker starting... (queue=%s)", TASK_QUEUE)

    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    # Redis 연결 대기
    for i in range(30):
        try:
            r.ping()
            default_logger.info("Redis connected")
            break
        except redis.ConnectionError:
            default_logger.info("Waiting for Redis... (%d/30)", i + 1)
            time.sleep(2)
    else:
        default_logger.error("Redis connection failed after 30 attempts")
        sys.exit(1)

    default_logger.info("AI Worker ready, listening for tasks...")

    while _running:
        try:
            # BLPOP: 태스크가 올 때까지 5초 대기 후 재시도
            result = r.blpop(TASK_QUEUE, timeout=5)
            if result is None:
                continue

            _, raw = result
            task = json.loads(raw)
            task_id = task.get("task_id", "unknown")

            try:
                response = handle_task(task)
            except Exception as e:
                default_logger.exception("[Task %s] Failed", task_id)
                response = {"status": "error", "task_id": task_id, "message": str(e)}

            # 결과를 Redis에 저장 (60초 TTL)
            r.setex(f"{RESULT_PREFIX}{task_id}", 60, json.dumps(response))

        except Exception:
            default_logger.exception("Worker loop error")
            time.sleep(1)

    default_logger.info("AI Worker stopped")


if __name__ == "__main__":
    main()
