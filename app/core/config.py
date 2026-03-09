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

    # OCR
    OCR_SECRET_KEY: str = ""
    OCR_INVOKE_URL: str = ""

    # 식약처 e약은요 OpenAPI (일반의약품)
    DATA_GO_KR_API_KEY_ENCODED: str = ""
    DATA_GO_KR_API_KEY_DECODED: str = ""

    # 식약처 의약품 제품 허가정보 상세 REST API (전문의약품 포함)
    DRUG_PRMSSN_API_KEY_ENCODED: str = ""
    DRUG_PRMSSN_API_KEY_DECODED: str = ""

    # 식품의약품안전처 의약품 제품 허가정보 (DrugPrdtPrmsnInfoService07)
    DRUG_PRDT_PRMSN_INFO_API_KEY_ENCODED: str = ""
    DRUG_PRDT_PRMSN_INFO_API_KEY_DECODED: str = ""

    # 식품의약품안전처 의약품안전사용서비스(DUR) 품목정보 (DURPrdlstInfoService03)
    DUR_PRDLST_INFO_API_KEY_ENCODED: str = ""
    DUR_PRDLST_INFO_API_KEY_DECODED: str = ""

    # 건강보험심사평가원 의약품사용정보조회서비스 (msupUserInfoService1.2)
    HIRA_MSUP_USER_INFO_API_KEY_ENCODED: str = ""
    HIRA_MSUP_USER_INFO_API_KEY_DECODED: str = ""

    # 건강보험심사평가원 의약품성분약효정보조회서비스 (msupCmpnMeftInfoService)
    HIRA_MSUP_CMPN_MEFT_INFO_API_KEY_ENCODED: str = ""
    HIRA_MSUP_CMPN_MEFT_INFO_API_KEY_DECODED: str = ""

    # LLM (GPT-4o-mini)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 1024
    OPENAI_TEMPERATURE: float = 0.3

    RAG_CONFIDENCE_THRESHOLD: float = 0.45

    # Kakao OAuth
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:5173/auth/kakao/callback"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/auth/google/callback"
