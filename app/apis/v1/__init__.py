from fastapi import APIRouter

from app.apis.v1.auth_routers import auth_router
from app.apis.v1.chat_routers import chat_router
from app.apis.v1.user_routers import user_router
from app.apis.v1.tts_routers import tts_router

from .vision import router as vision_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(vision_router)
v1_routers.include_router(chat_router)
v1_routers.include_router(tts_router)
