from __future__ import annotations

from app.core.config import Settings
from app.services import telegram_service
from app.services.telegram_service import TelegramService


def test_send_message_skips_without_token() -> None:
    service = TelegramService(Settings(telegram_bot_token=None))
    result = service.send_message("1001", "hello")
    assert result["status"] == "skipped"


def test_send_message_posts_with_retry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _stub_request_with_retry(method: str, url: str, **kwargs: object) -> dict[str, object]:
        calls.append({"method": method, "url": url, "kwargs": kwargs})
        return {"ok": True}

    monkeypatch.setattr(telegram_service, "request_with_retry", _stub_request_with_retry)

    service = TelegramService(
        Settings(
            telegram_bot_token="bot-token",
            http_timeout_seconds=3.0,
            http_max_retries=2,
        )
    )

    result = service.send_message("1001", "publish success")
    assert result == {"status": "sent"}
    assert calls
    assert calls[0]["method"] == "POST"
    assert "api.telegram.org" in str(calls[0]["url"])


def test_broadcast_skips_without_allowed_chat_ids() -> None:
    service = TelegramService(Settings(telegram_bot_token="bot-token", telegram_allowed_chat_ids=""))
    result = service.broadcast_message("hello")
    assert result["status"] == "skipped"


def test_broadcast_reports_posted_when_any_chat_succeeds(monkeypatch) -> None:
    service = TelegramService(Settings(telegram_bot_token="bot-token", telegram_allowed_chat_ids="1001,1002"))

    sent: list[tuple[str, str]] = []

    def _stub_send(chat_id: str, text: str) -> dict[str, str]:
        sent.append((chat_id, text))
        return {"status": "sent" if chat_id == "1001" else "error"}

    monkeypatch.setattr(service, "send_message", _stub_send)

    result = service.broadcast_message("published")
    assert result == {"status": "posted"}
    assert len(sent) == 2


def test_broadcast_reports_error_when_all_fail(monkeypatch) -> None:
    service = TelegramService(Settings(telegram_bot_token="bot-token", telegram_allowed_chat_ids="1001,1002"))

    def _stub_send(_chat_id: str, _text: str) -> dict[str, str]:
        return {"status": "error"}

    monkeypatch.setattr(service, "send_message", _stub_send)

    result = service.broadcast_message("published")
    assert result["status"] == "error"
