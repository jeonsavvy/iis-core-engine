from __future__ import annotations

from uuid import UUID

from app.core.config import Settings
from app.schemas.pipeline import TriggerRequest, TriggerSource
from app.schemas.telegram import TelegramWebhookResponse, TelegramWebhookUpdate
from app.services.http_client import request_with_retry
from app.services.pipeline_repository import PipelineRepository


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

    def handle_update(self, update: TelegramWebhookUpdate, repository: PipelineRepository) -> TelegramWebhookResponse:
        message = update.active_message()
        if message is None or not message.text:
            return TelegramWebhookResponse(status="ignored", detail="message.text is missing")

        chat_id = str(message.chat.id)
        command, argument = self._parse_command(message.text)

        if not self._is_allowed_chat(chat_id):
            audit_job = repository.create_audit_entry(
                source=TriggerSource.TELEGRAM,
                keyword=f"[BLOCKED] {message.text[:120]}",
                reason="telegram_chat_not_allowed",
                metadata={"chat_id": chat_id, "command": command, "argument": argument},
            )
            self.send_message(chat_id, "Unauthorized chat. Contact master_admin.")
            return TelegramWebhookResponse(
                status="blocked",
                detail="chat_id is not in TELEGRAM_ALLOWED_CHAT_IDS",
                pipeline_id=str(audit_job.pipeline_id),
                payload={"chat_id": chat_id},
            )

        if command == "/run":
            return self._handle_run(chat_id, argument, repository)

        if command == "/status":
            return self._handle_status(chat_id, argument, repository)

        self.send_message(chat_id, "Unknown command. Use /run <keyword> or /status <pipeline_id>")
        return TelegramWebhookResponse(status="unknown_command", detail=command or "empty")

    def _handle_run(self, chat_id: str, keyword: str, repository: PipelineRepository) -> TelegramWebhookResponse:
        if not keyword:
            self.send_message(chat_id, "Usage: /run <keyword>")
            return TelegramWebhookResponse(status="invalid", detail="missing keyword")

        trigger_request = TriggerRequest(
            keyword=keyword,
            source=TriggerSource.TELEGRAM,
            metadata={"chat_id": chat_id, "entry": "telegram_command"},
        )
        try:
            job = repository.create_pipeline(trigger_request)
        except ValueError as exc:
            self.send_message(chat_id, f"Invalid keyword: {exc}")
            return TelegramWebhookResponse(status="invalid", detail=str(exc))

        self.send_message(chat_id, f"Queued: {job.pipeline_id}")
        return TelegramWebhookResponse(
            status="queued",
            pipeline_id=str(job.pipeline_id),
            payload={"source": TriggerSource.TELEGRAM.value},
        )

    def _handle_status(self, chat_id: str, pipeline_id_arg: str, repository: PipelineRepository) -> TelegramWebhookResponse:
        if not pipeline_id_arg:
            self.send_message(chat_id, "Usage: /status <pipeline_id>")
            return TelegramWebhookResponse(status="invalid", detail="missing pipeline_id")

        try:
            pipeline_id = UUID(pipeline_id_arg)
        except ValueError:
            self.send_message(chat_id, "Invalid pipeline_id format.")
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        job = repository.get_pipeline(pipeline_id)
        if job is None:
            self.send_message(chat_id, "Pipeline not found.")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")

        self.send_message(
            chat_id,
            f"Pipeline {job.pipeline_id}\nstatus={job.status.value}\nsource={job.source.value}\nerror={job.error_reason or '-'}",
        )
        return TelegramWebhookResponse(
            status="status_reported",
            pipeline_id=str(job.pipeline_id),
            payload={"pipeline_status": job.status.value},
        )

    def _is_allowed_chat(self, chat_id: str) -> bool:
        allowed = self.settings.telegram_allowed_chat_id_set()
        if not allowed:
            return False
        return chat_id in allowed

    @staticmethod
    def _parse_command(text: str) -> tuple[str, str]:
        raw = text.strip()
        if not raw:
            return "", ""

        split = raw.split(maxsplit=1)
        command_part = split[0].split("@", maxsplit=1)[0].lower()
        argument = split[1].strip() if len(split) > 1 else ""
        return command_part, argument
