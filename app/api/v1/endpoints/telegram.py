from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import get_pipeline_repository
from app.core.config import get_settings
from app.schemas.telegram import TelegramWebhookResponse, TelegramWebhookUpdate
from app.services.pipeline_repository import PipelineRepository
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    payload: TelegramWebhookUpdate,
    repository: PipelineRepository = Depends(get_pipeline_repository),
    x_telegram_secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> TelegramWebhookResponse:
    settings = get_settings()

    if settings.telegram_webhook_secret and x_telegram_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid telegram webhook secret token")

    service = TelegramService(settings)
    return service.handle_update(payload, repository)
