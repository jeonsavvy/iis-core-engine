from fastapi import HTTPException

from app.api.deps import get_pipeline_repository
from app.api.v1.endpoints.telegram import telegram_webhook
from app.core.config import get_settings
from app.schemas.telegram import TelegramWebhookUpdate


def _prepare_env(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_CONTROL_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "1001")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "2002")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")


def test_telegram_webhook_returns_503_when_secret_not_configured(monkeypatch) -> None:
    _prepare_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "")
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    payload = TelegramWebhookUpdate.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": 1001, "type": "private"},
                "from": {"id": 2002, "username": "iis-admin"},
                "text": "/run webhook test",
            },
        }
    )

    try:
        telegram_webhook(payload, get_pipeline_repository(), x_telegram_secret=None)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("expected HTTPException when webhook secret is not configured")

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_telegram_webhook_requires_secret_when_configured(monkeypatch) -> None:
    _prepare_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-123")
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    payload = TelegramWebhookUpdate.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": 1001, "type": "private"},
                "from": {"id": 2002, "username": "iis-admin"},
                "text": "/run webhook test",
            },
        }
    )
    repository = get_pipeline_repository()

    try:
        telegram_webhook(payload, repository, x_telegram_secret=None)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("expected HTTPException for missing webhook token")

    allowed = telegram_webhook(payload, repository, x_telegram_secret="secret-123")
    assert allowed.status == "queued"

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()
