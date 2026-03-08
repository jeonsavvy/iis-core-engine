from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import Settings
from app.services.http_client import ExternalCallError, request_with_retry


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _is_usable_photo_url(photo_url: str | None) -> bool:
        if not photo_url or not photo_url.strip():
            return False
        parsed = urlparse(photo_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        return not parsed.path.casefold().endswith(".svg")

    @staticmethod
    def _fallback_marketing_line(*, title: str, genre: str) -> str:
        genre_text = genre.strip() or "브라우저"
        return f"{title} · {genre_text} 감성의 새 런치 빌드를 지금 바로 플레이해보세요."

    @classmethod
    def _build_launch_text(
        cls,
        *,
        title: str,
        marketing_line: str,
        play_url: str,
        public_url: str | None = None,
        genre: str = "",
        slug: str = "",
    ) -> str:
        normalized_title = title.strip() or "New Launch"
        normalized_line = marketing_line.strip() or cls._fallback_marketing_line(title=normalized_title, genre=genre)
        lines = [normalized_title, normalized_line, "", f"Play\n{play_url.strip()}"]
        normalized_public = (public_url or "").strip()
        if normalized_public and normalized_public != play_url.strip():
            lines.extend(["", f"Public\n{normalized_public}"])
        return "\n".join(lines).strip()

    def send_message(self, chat_id: str, text: str, *, disable_notification: bool = False) -> dict[str, str]:
        if not self.settings.telegram_bot_token:
            return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN is not configured."}

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        try:
            request_with_retry(
                "POST",
                url,
                timeout_seconds=self.settings.http_timeout_seconds,
                max_retries=self.settings.http_max_retries,
                json={"chat_id": chat_id, "text": text, "disable_notification": disable_notification},
            )
            return {"status": "sent"}
        except ExternalCallError as exc:
            return {"status": "error", "reason": str(exc)}

    def send_photo(
        self,
        chat_id: str,
        *,
        photo_url: str,
        caption: str,
        disable_notification: bool = False,
    ) -> dict[str, str]:
        if not self.settings.telegram_bot_token:
            return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN is not configured."}

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendPhoto"
        try:
            request_with_retry(
                "POST",
                url,
                timeout_seconds=self.settings.http_timeout_seconds,
                max_retries=self.settings.http_max_retries,
                json={
                    "chat_id": chat_id,
                    "photo": photo_url,
                    "caption": caption[:900],
                    "disable_notification": disable_notification,
                },
            )
            return {"status": "sent"}
        except ExternalCallError as exc:
            return {"status": "error", "reason": str(exc)}

    def broadcast_message(self, text: str, *, disable_notification: bool = False) -> dict[str, str]:
        allowed = self.settings.telegram_allowed_chat_id_set()
        if not allowed:
            return {"status": "skipped", "reason": "No allowed chat IDs configured for broadcast."}

        success_count = 0
        for chat_id in allowed:
            result = self.send_message(chat_id, text, disable_notification=disable_notification)
            if result.get("status") == "sent":
                success_count += 1

        if success_count > 0:
            return {"status": "posted"}
        return {"status": "error", "reason": "Failed to send broadcast to any allowed chats."}

    def broadcast_launch_announcement(
        self,
        *,
        title: str,
        marketing_line: str,
        play_url: str,
        photo_url: str | None = None,
        public_url: str | None = None,
        genre: str = "",
        slug: str = "",
        disable_notification: bool = False,
    ) -> dict[str, str]:
        allowed = self.settings.telegram_allowed_chat_id_set()
        if not allowed:
            return {"status": "skipped", "reason": "No allowed chat IDs configured for broadcast."}

        launch_text = self._build_launch_text(
            title=title,
            marketing_line=marketing_line,
            play_url=play_url,
            public_url=public_url,
            genre=genre,
            slug=slug,
        )
        usable_photo_url = (photo_url or "").strip() if self._is_usable_photo_url(photo_url) else None

        success_count = 0
        for chat_id in allowed:
            result = (
                self.send_photo(
                    chat_id,
                    photo_url=usable_photo_url,
                    caption=launch_text,
                    disable_notification=disable_notification,
                )
                if usable_photo_url
                else self.send_message(chat_id, launch_text, disable_notification=disable_notification)
            )
            if result.get("status") != "sent" and usable_photo_url:
                result = self.send_message(chat_id, launch_text, disable_notification=disable_notification)
            if result.get("status") == "sent":
                success_count += 1

        if success_count > 0:
            return {"status": "posted"}
        return {"status": "error", "reason": "Failed to send launch announcement to any allowed chats."}
