from uuid import UUID

from app.core.config import Settings
from app.schemas.pipeline import PipelineStatus, TriggerSource
from app.schemas.telegram import TelegramWebhookUpdate
from app.services.pipeline_repository import PipelineRepository
from app.services.telegram_service import TelegramService


def make_update(text: str, chat_id: int = 1001) -> TelegramWebhookUpdate:
    return TelegramWebhookUpdate.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id, "type": "private"},
                "text": text,
            },
        }
    )


def test_run_command_queues_pipeline_from_telegram() -> None:
    settings = Settings(telegram_allowed_chat_ids="1001")
    repository = PipelineRepository()
    service = TelegramService(settings)

    result = service.handle_update(make_update("/run neon puzzle"), repository)

    assert result.status == "queued"
    assert result.pipeline_id is not None

    job = repository.get_pipeline(UUID(result.pipeline_id))
    assert job is not None
    assert job.source == TriggerSource.TELEGRAM
    assert job.status == PipelineStatus.QUEUED
    assert job.keyword == "neon puzzle"


def test_blocked_chat_creates_audit_entry() -> None:
    settings = Settings(telegram_allowed_chat_ids="1001")
    repository = PipelineRepository()
    service = TelegramService(settings)

    result = service.handle_update(make_update("/run blocked", chat_id=9999), repository)

    assert result.status == "blocked"
    assert result.pipeline_id is not None

    audit_job = repository.get_pipeline(UUID(result.pipeline_id))
    assert audit_job is not None
    assert audit_job.source == TriggerSource.TELEGRAM
    assert audit_job.status == PipelineStatus.SKIPPED
    assert audit_job.error_reason == "telegram_chat_not_allowed"


def test_status_command_reports_pipeline_status() -> None:
    settings = Settings(telegram_allowed_chat_ids="1001")
    repository = PipelineRepository()
    service = TelegramService(settings)

    queued = service.handle_update(make_update("/run score attack"), repository)
    assert queued.pipeline_id is not None

    status_result = service.handle_update(make_update(f"/status {queued.pipeline_id}"), repository)

    assert status_result.status == "status_reported"
    assert status_result.pipeline_id == queued.pipeline_id
    assert status_result.payload["pipeline_status"] == PipelineStatus.QUEUED.value


def test_run_command_rejects_forbidden_keyword() -> None:
    settings = Settings(telegram_allowed_chat_ids="1001", trigger_forbidden_keywords="banned")
    repository = PipelineRepository(settings=settings)
    service = TelegramService(settings)

    result = service.handle_update(make_update("/run banned idea"), repository)

    assert result.status == "invalid"
    assert result.detail == "keyword_contains_blocked_term"
    assert result.pipeline_id is None
