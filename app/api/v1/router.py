from fastapi import APIRouter

from app.api.v1.endpoints import games, health, pipelines, telegram
from app.api.v1.session_router import router as session_router

router = APIRouter()
router.include_router(health.router)
router.include_router(pipelines.router)
router.include_router(games.router)
router.include_router(telegram.router)
router.include_router(session_router)
