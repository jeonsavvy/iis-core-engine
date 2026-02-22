from fastapi import APIRouter

from app.api.v1.endpoints import games, health, pipelines, telegram

router = APIRouter()
router.include_router(health.router)
router.include_router(pipelines.router)
router.include_router(games.router)
router.include_router(telegram.router)
