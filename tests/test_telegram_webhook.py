from fastapi.testclient import TestClient

from app.api.deps import get_pipeline_repository
from app.core.config import get_settings
from app.main import app


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

    client = TestClient(app)
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 1001, "type": "private"},
            "from": {"id": 2002, "username": "iis-admin"},
            "text": "/run webhook test",
        },
    }
    response = client.post("/api/v1/telegram/webhook", json=payload)
    assert response.status_code == 503

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_telegram_webhook_requires_secret_when_configured(monkeypatch) -> None:
    _prepare_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-123")
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    client = TestClient(app)
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 1001, "type": "private"},
            "from": {"id": 2002, "username": "iis-admin"},
            "text": "/run webhook test",
        },
    }

    forbidden = client.post("/api/v1/telegram/webhook", json=payload)
    assert forbidden.status_code == 403

    allowed = client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "queued"

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()
