from uuid import UUID

from fastapi import HTTPException

from app.api.deps import get_pipeline_repository
from app.api.v1.endpoints.pipelines import approve_pipeline_stage, control_pipeline, trigger_pipeline
from app.core.config import get_settings
from app.schemas.pipeline import PipelineControlRequest, PipelineStatus, StageApprovalRequest, TriggerRequest


def _reset_app_state() -> None:
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_approve_stage_for_manual_pipeline() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    trigger = trigger_pipeline(
        TriggerRequest(keyword="manual approval api", source="console", execution_mode="manual"),
        repository,
    )
    pipeline_id = str(trigger.pipeline_id)

    approve = approve_pipeline_stage(
        UUID(pipeline_id),
        StageApprovalRequest(stage="plan"),
        repository,
    )
    assert approve.approved_stage.value == "plan"
    assert approve.execution_mode.value == "manual"

    _reset_app_state()


def test_approve_stage_rejected_for_auto_pipeline() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    trigger = trigger_pipeline(
        TriggerRequest(keyword="auto mode", source="console", execution_mode="auto"),
        repository,
    )
    pipeline_id = str(trigger.pipeline_id)

    try:
        approve_pipeline_stage(
            UUID(pipeline_id),
            StageApprovalRequest(stage="plan"),
            repository,
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "manual_approval_not_enabled"
    else:
        raise AssertionError("expected HTTPException for auto execution mode")

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


def test_control_resume_approves_waiting_stage() -> None:
    _reset_app_state()
    repository = get_pipeline_repository()

    trigger = trigger_pipeline(
        TriggerRequest(keyword="resume waiting", source="console", execution_mode="manual"),
        repository,
    )
    pipeline_id = str(trigger.pipeline_id)

    repository.update_pipeline_metadata(
        UUID(pipeline_id),
        metadata_update={"waiting_for_stage": "plan"},
        status=PipelineStatus.SKIPPED,
        error_reason="awaiting_approval:plan",
    )

    resume = control_pipeline(
        UUID(pipeline_id),
        PipelineControlRequest(action="resume"),
        repository,
    )
    assert resume.action.value == "resume"
    assert resume.status == PipelineStatus.QUEUED
    assert resume.waiting_for_stage is None

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
