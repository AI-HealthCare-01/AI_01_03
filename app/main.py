import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse

from app.apis.integration_routers import integration_router
from app.apis.v1 import v1_routers
from app.db.databases import initialize_tortoise

try:
    import orjson as _orjson  # noqa: F401

    default_response_class = ORJSONResponse
except Exception:  # pragma: no cover - 선택적 의존성 방어
    default_response_class = JSONResponse
logger = logging.getLogger("main")

import os

_is_prod = os.getenv("ENV", "local") == "production"

app = FastAPI(
    default_response_class=default_response_class,
    docs_url=None if _is_prod else "/api/docs",
    redoc_url=None if _is_prod else "/api/redoc",
    openapi_url=None if _is_prod else "/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://yoyak-med-mentor.vercel.app",
        "https://www.yoyak.site",
        "https://yoyak.site",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_tortoise(app)

app.include_router(integration_router)
app.include_router(v1_routers)


@app.on_event("startup")
async def warmup_rag() -> None:
    """서버 시작 시 RAG 인덱스 + 임베딩 모델 미리 로드."""
    from app.services.rag_search import RAGSearchService

    rag = RAGSearchService.get_instance()
    if rag.is_ready:
        logger.info("RAG 워밍업 완료: 인덱스 + 임베딩 모델 로드됨")
    else:
        logger.warning("RAG 워밍업 실패: 인덱스 미로드")
