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

app = FastAPI(
    default_response_class=default_response_class,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:8082",
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
