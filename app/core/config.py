import os
import uuid
import zoneinfo
from dataclasses import field
from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../env"), env_file_encoding="utf-8", extra="allow")

    ENV: Env = Env.LOCAL
    SECRET_KEY: str = f"default-secret-key{uuid.uuid4().hex}"
    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    TEMPLATE_DIR: str = os.path.join(Path(__file__).resolve().parent.parent, "templates")

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "pw1234"
    DB_NAME: str = "ai_health"
    DB_CONNECT_TIMEOUT: int = 5
    DB_CONNECTION_POOL_MAXSIZE: int = 10

    COOKIE_DOMAIN: str = "localhost"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 14 * 24 * 60
    JWT_LEEWAY: int = 5

    OCR_SECRET_KEY: str = ""
    OCR_INVOKE_URL: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_VISION_MODEL: str = "gpt-4o-mini"

    VISION_OPENAI_TIMEOUT_SEC: float = 8.0
    VISION_OPENAI_RETRY_COUNT: int = 2
    VISION_OPENAI_BACKOFF_SEC: float = 0.5
    VISION_OPENAI_MAX_TOKENS: int = 500

    VISION_DETECT_MODEL_PATH: str = "yolov8n.pt"
    VISION_DETECT_CONF_THRES: float = 0.25
    VISION_MAX_DETECTIONS: int = 5
    VISION_TOP_K: int = 3
    VISION_MAX_IMAGE_SIDE: int = 1280
    VISION_ENABLE_FULL_IMAGE_FALLBACK: bool = True
    VISION_DISCLAIMER: str = "본 서비스는 복약 보조 수단입니다."

    VISION_CLASSIFIER_ENABLED: bool = False
    VISION_CLASSIFIER_MODEL_PATH: str = "runs/classify/runs/classify/pill_cls_finetune_v1/weights/best.pt"
    VISION_CLASSIFIER_LABELS_PATH: str = "runs/classify/runs/classify/pill_cls_finetune_v1/labels.json"
    VISION_MEDICATION_MAP_PATH: str = "app/resources/vision_medication_map.json"
    VISION_CLASSIFIER_TOP_K: int = 3
    VISION_CLASSIFIER_WEIGHT: float = 0.7
