from fastapi.testclient import TestClient

from app.api.deps import get_pipeline_repository
from app.core.config import get_settings
from app.main import app


def test_telegram_webhook_requires_secret_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "1001")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-123")
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    client = TestClient(app)
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 1001, "type": "private"},
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
