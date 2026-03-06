from fastapi import FastAPI
from fastapi.responses import JSONResponse, ORJSONResponse

from app.apis.integration_routers import integration_router
from app.apis.v1 import v1_routers
from app.db.databases import initialize_tortoise

try:
    import orjson as _orjson  # noqa: F401

    default_response_class = ORJSONResponse
except Exception:  # pragma: no cover - 선택적 의존성 방어
    default_response_class = JSONResponse

app = FastAPI(
    default_response_class=default_response_class,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
initialize_tortoise(app)

app.include_router(integration_router)
app.include_router(v1_routers)
