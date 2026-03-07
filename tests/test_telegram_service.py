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

    def _stub_send(chat_id: str, text: str, *, disable_notification: bool = False) -> dict[str, str]:
        sent.append((chat_id, text))
        return {"status": "sent" if chat_id == "1001" else "error"}

    monkeypatch.setattr(service, "send_message", _stub_send)

    result = service.broadcast_message("published")
    assert result == {"status": "posted"}
    assert len(sent) == 2


def test_broadcast_reports_error_when_all_fail(monkeypatch) -> None:
    service = TelegramService(Settings(telegram_bot_token="bot-token", telegram_allowed_chat_ids="1001,1002"))

    def _stub_send(_chat_id: str, _text: str, *, disable_notification: bool = False) -> dict[str, str]:
        return {"status": "error"}

    monkeypatch.setattr(service, "send_message", _stub_send)

    result = service.broadcast_message("published")
    assert result["status"] == "error"


def test_send_photo_posts_with_retry(monkeypatch) -> None:
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

    result = service.send_photo("1001", photo_url="https://cdn.example.com/shot.png", caption="launch caption")
    assert result == {"status": "sent"}
    assert calls
    assert calls[0]["method"] == "POST"
    request_json = calls[0]["kwargs"]  # type: ignore[index]
    assert isinstance(request_json, dict)
    assert request_json["json"] == {
        "chat_id": "1001",
        "photo": "https://cdn.example.com/shot.png",
        "caption": "launch caption",
        "disable_notification": False,
    }


def test_broadcast_launch_announcement_uses_photo_when_available(monkeypatch) -> None:
    service = TelegramService(Settings(telegram_bot_token="bot-token", telegram_allowed_chat_ids="1001,1002"))

    sent_photos: list[tuple[str, str, str]] = []
    sent_messages: list[tuple[str, str]] = []

    def _stub_send_photo(chat_id: str, *, photo_url: str, caption: str, disable_notification: bool = False) -> dict[str, str]:
        sent_photos.append((chat_id, photo_url, caption))
        return {"status": "sent" if chat_id == "1001" else "error"}

    def _stub_send_message(chat_id: str, text: str, *, disable_notification: bool = False) -> dict[str, str]:
        sent_messages.append((chat_id, text))
        return {"status": "sent"}

    monkeypatch.setattr(service, "send_photo", _stub_send_photo)
    monkeypatch.setattr(service, "send_message", _stub_send_message)

    result = service.broadcast_launch_announcement(
        title="Neon Drift",
        marketing_line="네온 서킷 위를 질주하는 하이스피드 아케이드 런치",
        play_url="https://arcade.example.com/play/neon-drift",
        photo_url="https://cdn.example.com/neon-drift.png",
        genre="racing",
        slug="neon-drift",
    )

    assert result == {"status": "posted"}
    assert len(sent_photos) == 2
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "1002"
    assert "Neon Drift" in sent_photos[0][2]
    assert "https://arcade.example.com/play/neon-drift" in sent_photos[0][2]


def test_broadcast_launch_announcement_falls_back_to_text_when_photo_missing(monkeypatch) -> None:
    service = TelegramService(Settings(telegram_bot_token="bot-token", telegram_allowed_chat_ids="1001"))

    sent_messages: list[tuple[str, str]] = []

    def _stub_send_message(chat_id: str, text: str, *, disable_notification: bool = False) -> dict[str, str]:
        sent_messages.append((chat_id, text))
        return {"status": "sent"}

    monkeypatch.setattr(service, "send_message", _stub_send_message)

    result = service.broadcast_launch_announcement(
        title="Aether Courier",
        marketing_line="바다와 섬 위를 가르는 로우폴리 플라이트 런치",
        play_url="https://arcade.example.com/play/aether-courier",
        photo_url=None,
        genre="flight",
        slug="aether-courier",
    )

    assert result == {"status": "posted"}
    assert len(sent_messages) == 1
    assert "Aether Courier" in sent_messages[0][1]
    assert "https://arcade.example.com/play/aether-courier" in sent_messages[0][1]
