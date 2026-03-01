from uuid import UUID

from fastapi import HTTPException

from app.api.deps import get_pipeline_repository
from app.api.v1.endpoints.pipelines import approve_pipeline_stage, control_pipeline, trigger_pipeline
from app.core.config import get_settings
from app.schemas.pipeline import PipelineControlRequest, PipelineStatus, TriggerRequest


def _reset_app_state() -> None:
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_approve_endpoint_returns_410_gone() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()
    trigger = trigger_pipeline(
        TriggerRequest(keyword="approval removed", source="console", execution_mode="auto"),
        repository,
    )

    try:
        approve_pipeline_stage(trigger.pipeline_id)
    except HTTPException as exc:
        assert exc.status_code == 410
        assert exc.detail == "approval_api_removed"
    else:
        raise AssertionError("expected HTTPException for removed approval endpoint")

    _reset_app_state()


def test_control_pause_sets_operator_control_flag() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    trigger = trigger_pipeline(
        TriggerRequest(keyword="pause flow", source="console", execution_mode="auto"),
        repository,
    )
    pipeline_id = str(trigger.pipeline_id)

    pause = control_pipeline(
        UUID(pipeline_id),
        PipelineControlRequest(action="pause"),
        repository,
    )
    assert pause.action.value == "pause"

    job = repository.get_pipeline(UUID(pipeline_id))
    assert job is not None
    operator_control = job.metadata.get("operator_control")
    assert isinstance(operator_control, dict)
    assert operator_control.get("pause_requested") is True

    _reset_app_state()


def test_control_cancel_immediately_errors_queued_pipeline() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    trigger = trigger_pipeline(
        TriggerRequest(keyword="cancel queued", source="console", execution_mode="auto"),
        repository,
    )
    pipeline_id = str(trigger.pipeline_id)

    cancel = control_pipeline(
        UUID(pipeline_id),
        PipelineControlRequest(action="cancel"),
        repository,
    )
    assert cancel.status == PipelineStatus.ERROR
    assert cancel.error_reason == "cancelled_by_operator"

    _reset_app_state()


def test_control_resume_requeues_skipped_pipeline() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    trigger = trigger_pipeline(
        TriggerRequest(keyword="resume skipped", source="console", execution_mode="auto"),
        repository,
    )
    pipeline_id = str(trigger.pipeline_id)

    repository.update_pipeline_metadata(
        UUID(pipeline_id),
        metadata_update={"operator_control": {"pause_requested": False, "cancel_requested": False}},
        status=PipelineStatus.SKIPPED,
        error_reason="paused_by_operator",
    )

    resume = control_pipeline(
        UUID(pipeline_id),
        PipelineControlRequest(action="resume"),
        repository,
    )
    assert resume.action.value == "resume"
    assert resume.status == PipelineStatus.QUEUED

    _reset_app_state()


def test_trigger_pipeline_idempotency_key_reuses_pipeline() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    first = trigger_pipeline(
        TriggerRequest(keyword="idempotent trigger", source="console"),
        repository,
        "idem-trigger-0001",
    )
    second = trigger_pipeline(
        TriggerRequest(keyword="idempotent trigger", source="console"),
        repository,
        "idem-trigger-0001",
    )

    assert first.pipeline_id == second.pipeline_id
    assert first.request_id is not None
    assert first.request_id == second.request_id

    _reset_app_state()


def test_trigger_pipeline_rejects_invalid_idempotency_key_length() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    try:
        trigger_pipeline(
            TriggerRequest(keyword="idempotency too short", source="console"),
            repository,
            "short",
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "idempotency_key_invalid_length"
    else:
        raise AssertionError("expected HTTPException for invalid idempotency key length")

    _reset_app_state()


def test_trigger_pipeline_rejects_too_long_idempotency_key() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    try:
        trigger_pipeline(
            TriggerRequest(keyword="idempotency too long", source="console"),
            repository,
            "x" * 129,
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "idempotency_key_invalid_length"
    else:
        raise AssertionError("expected HTTPException for invalid idempotency key length")

    _reset_app_state()


def test_trigger_pipeline_header_idempotency_key_overrides_payload_key() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    first = trigger_pipeline(
        TriggerRequest(keyword="header key wins", source="console", idempotency_key="payload-key-0001"),
        repository,
        "header-key-0001",
    )
    second = trigger_pipeline(
        TriggerRequest(keyword="header key wins", source="console", idempotency_key="payload-key-0002"),
        repository,
        "header-key-0001",
    )

    assert first.pipeline_id == second.pipeline_id
    assert first.request_id == second.request_id
    stored = repository.get_pipeline(first.pipeline_id)
    assert stored is not None
    assert stored.metadata.get("idempotency_key") == "header-key-0001"

    _reset_app_state()


def test_control_returns_structured_404_code_for_unknown_pipeline() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    try:
        control_pipeline(
            UUID("00000000-0000-0000-0000-000000000001"),
            PipelineControlRequest(action="pause"),
            repository,
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert isinstance(exc.detail, dict)
        assert exc.detail.get("code") == "pipeline_not_found"
    else:
        raise AssertionError("expected HTTPException for unknown pipeline")

    _reset_app_state()
