from __future__ import annotations

from app.core.config import Settings
from app.services.http_client import request_with_retry


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_message(self, chat_id: str, text: str) -> dict[str, str]:
        if not self.settings.telegram_bot_token:
            return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN is not configured."}

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        request_with_retry(
            "POST",
            url,
            timeout_seconds=self.settings.http_timeout_seconds,
            max_retries=self.settings.http_max_retries,
            json={"chat_id": chat_id, "text": text},
        )
        return {"status": "sent"}

    def broadcast_message(self, text: str) -> dict[str, str]:
        allowed = self.settings.telegram_allowed_chat_id_set()
        if not allowed:
            return {"status": "skipped", "reason": "No allowed chat IDs configured for broadcast."}

        success_count = 0
        for chat_id in allowed:
            result = self.send_message(chat_id, text)
            if result.get("status") == "sent":
                success_count += 1

        if success_count > 0:
            return {"status": "posted"}
        return {"status": "error", "reason": "Failed to send broadcast to any allowed chats."}
