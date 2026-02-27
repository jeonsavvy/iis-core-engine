from __future__ import annotations

from uuid import UUID

from app.core.config import Settings
from app.schemas.pipeline import PipelineStatus, TriggerRequest, TriggerSource
from app.schemas.telegram import TelegramWebhookUpdate
from app.services.pipeline_repository import PipelineRepository
from app.services.telegram_service import TelegramService


class StubTelegramService(TelegramService):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.sent_messages: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> dict[str, str]:
        self.sent_messages.append((chat_id, text))
        return {"status": "sent"}


def make_update(text: str, *, chat_id: int = 1001, user_id: int = 2002) -> TelegramWebhookUpdate:
    return TelegramWebhookUpdate(
        update_id=1,
        message={
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "username": "iis-admin"},
            "text": text,
        },
    )


def _default_settings(**overrides) -> Settings:
    data = {
        "telegram_control_enabled": True,
        "telegram_webhook_secret": "secret-123",
        "telegram_allowed_chat_ids": "1001",
        "telegram_allowed_user_ids": "2002",
        "telegram_allow_dangerous_commands": True,
        "telegram_confirm_secret": "confirm-123",
        "telegram_confirm_ttl_seconds": 120,
    }
    data.update(overrides)
    return Settings(**data)


def test_run_command_queues_pipeline_for_allowed_user_and_chat() -> None:
    settings = _default_settings()
    repository = PipelineRepository(settings=settings)
    service = StubTelegramService(settings)

    result = service.handle_update(make_update("/run neon puzzle"), repository)

    assert result.status == "queued"
    assert result.pipeline_id is not None

    job = repository.get_pipeline(UUID(result.pipeline_id))
    assert job is not None
    assert job.source == TriggerSource.TELEGRAM
    assert job.status == PipelineStatus.QUEUED
    assert job.keyword == "neon puzzle"


def test_blocked_user_creates_audit_entry() -> None:
    settings = _default_settings()
    repository = PipelineRepository(settings=settings)
    service = StubTelegramService(settings)

    result = service.handle_update(make_update("/run blocked", user_id=9999), repository)

    assert result.status == "blocked"
    assert result.detail == "telegram_user_not_allowed"
    assert result.pipeline_id is not None

    audit_job = repository.get_pipeline(UUID(result.pipeline_id))
    assert audit_job is not None
    assert audit_job.status == PipelineStatus.SKIPPED
    assert audit_job.error_reason == "telegram_user_not_allowed"


def test_missing_webhook_secret_blocks_control_commands() -> None:
    settings = _default_settings(telegram_webhook_secret=None)
    repository = PipelineRepository(settings=settings)
    service = StubTelegramService(settings)

    result = service.handle_update(make_update("/run blocked"), repository)

    assert result.status == "blocked"
    assert result.detail == "telegram_webhook_secret_required"
    assert result.pipeline_id is not None


def test_retry_requires_confirm_then_confirm_executes_retry() -> None:
    settings = _default_settings()
    repository = PipelineRepository(settings=settings)
    service = StubTelegramService(settings)

    job = repository.create_pipeline(TriggerRequest(keyword="retry-me"))
    repository.mark_pipeline_status(job.pipeline_id, PipelineStatus.ERROR, error_reason="forced_error")

    request = service.handle_update(make_update(f"/retry {job.pipeline_id}"), repository)
    assert request.status == "confirm_required"

    confirm_message = service.sent_messages[-1][1]
    token = confirm_message.split("/confirm ", maxsplit=1)[1].strip()
    confirm = service.handle_update(make_update(f"/confirm {token}"), repository)

    assert confirm.status == "ok"
    updated = repository.get_pipeline(job.pipeline_id)
    assert updated is not None
    assert updated.status == PipelineStatus.QUEUED
    assert updated.error_reason is None


def test_run_command_rejects_forbidden_keyword() -> None:
    settings = _default_settings(trigger_forbidden_keywords="banned")
    repository = PipelineRepository(settings=settings)
    service = StubTelegramService(settings)

    result = service.handle_update(make_update("/run banned idea"), repository)

    assert result.status == "invalid"
    assert result.detail == "keyword_contains_blocked_term"
    assert result.pipeline_id is None


def test_start_command_returns_help_message() -> None:
    settings = _default_settings()
    repository = PipelineRepository(settings=settings)
    service = StubTelegramService(settings)

    result = service.handle_update(make_update("/start"), repository)

    assert result.status == "help"
    assert service.sent_messages
    assert "IIS 제어 봇 명령 안내" in service.sent_messages[-1][1]
