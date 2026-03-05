import logging

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.apis.integration_routers import integration_router
from app.apis.v1 import v1_routers
from app.db.databases import initialize_tortoise

logger = logging.getLogger("main")

app = FastAPI(
    default_response_class=ORJSONResponse, docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json"
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
