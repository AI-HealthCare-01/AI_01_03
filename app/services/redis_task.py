"""
Redis 기반 AI Worker 태스크 클라이언트.

FastAPI → Redis 큐(ai:tasks)에 태스크를 넣고,
ai-worker가 처리한 결과를 ai:result:{task_id}에서 폴링합니다.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import redis

from app.core import config, default_logger

TASK_QUEUE = "ai:tasks"
RESULT_PREFIX = "ai:result:"

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis_client


async def enqueue_and_wait(
    task_type: str,
    payload: dict[str, Any],
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """태스크를 Redis 큐에 넣고 결과가 올 때까지 폴링합니다.

    Args:
        task_type: 태스크 유형 (vision_detect, vision_classify, ping 등)
        payload: 태스크에 전달할 데이터 (task_type, task_id 제외)
        timeout: 결과 대기 최대 시간 (초). None이면 config 기본값 사용.

    Returns:
        ai-worker가 반환한 결과 dict

    Raises:
        TimeoutError: 지정 시간 내에 결과가 오지 않은 경우
        RuntimeError: ai-worker가 에러를 반환한 경우
    """
    if timeout is None:
        timeout = config.VISION_TASK_TIMEOUT

    task_id = uuid.uuid4().hex
    task = {"task_id": task_id, "type": task_type, **payload}

    r = _get_redis()
    r.rpush(TASK_QUEUE, json.dumps(task))
    default_logger.info("[RedisTask] Enqueued %s (task_id=%s)", task_type, task_id)

    result_key = f"{RESULT_PREFIX}{task_id}"
    poll_interval = 0.2  # 200ms 간격 폴링
    elapsed = 0.0

    while elapsed < timeout:
        raw = r.get(result_key)
        if raw is not None:
            r.delete(result_key)
            result = json.loads(raw)
            default_logger.info(
                "[RedisTask] Got result for %s (task_id=%s, status=%s)",
                task_type,
                task_id,
                result.get("status"),
            )
            if result.get("status") == "error":
                raise RuntimeError(f"AI Worker error ({task_type}): {result.get('message', 'unknown')}")
            return result

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"AI Worker 태스크 응답 시간 초과 ({task_type}, {timeout}s)")
