from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_pipeline_repository
from app.core.config import get_settings
from app.main import app
from app.schemas.pipeline import PipelineStatus


def _reset_app_state() -> None:
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_approve_stage_for_manual_pipeline() -> None:
    _reset_app_state()
    client = TestClient(app)

    trigger = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "manual approval api", "source": "console", "execution_mode": "manual"},
    )
    assert trigger.status_code == 202
    pipeline_id = trigger.json()["pipeline_id"]

    approve = client.post(
        f"/api/v1/pipelines/{pipeline_id}/approvals",
        json={"stage": "plan"},
    )
    assert approve.status_code == 200
    assert approve.json()["approved_stage"] == "plan"
    assert approve.json()["execution_mode"] == "manual"

    _reset_app_state()


def test_approve_stage_rejected_for_auto_pipeline() -> None:
    _reset_app_state()
    client = TestClient(app)

    trigger = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "auto mode", "source": "console", "execution_mode": "auto"},
    )
    assert trigger.status_code == 202
    pipeline_id = trigger.json()["pipeline_id"]

    approve = client.post(
        f"/api/v1/pipelines/{pipeline_id}/approvals",
        json={"stage": "plan"},
    )
    assert approve.status_code == 409
    assert approve.json()["detail"] == "manual_approval_not_enabled"

    _reset_app_state()


def test_control_pause_sets_operator_control_flag() -> None:
    _reset_app_state()
    client = TestClient(app)

    trigger = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "pause flow", "source": "console", "execution_mode": "auto"},
    )
    assert trigger.status_code == 202
    pipeline_id = trigger.json()["pipeline_id"]

    pause = client.post(
        f"/api/v1/pipelines/{pipeline_id}/controls",
        json={"action": "pause"},
    )
    assert pause.status_code == 200
    assert pause.json()["action"] == "pause"

    repository = get_pipeline_repository()
    job = repository.get_pipeline(UUID(pipeline_id))
    assert job is not None
    operator_control = job.metadata.get("operator_control")
    assert isinstance(operator_control, dict)
    assert operator_control.get("pause_requested") is True

    _reset_app_state()


def test_control_cancel_immediately_errors_queued_pipeline() -> None:
    _reset_app_state()
    client = TestClient(app)

    trigger = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "cancel queued", "source": "console", "execution_mode": "auto"},
    )
    assert trigger.status_code == 202
    pipeline_id = trigger.json()["pipeline_id"]

    cancel = client.post(
        f"/api/v1/pipelines/{pipeline_id}/controls",
        json={"action": "cancel"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == PipelineStatus.ERROR.value
    assert cancel.json()["error_reason"] == "cancelled_by_operator"

    _reset_app_state()


def test_control_resume_approves_waiting_stage() -> None:
    _reset_app_state()
    client = TestClient(app)

    trigger = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "resume waiting", "source": "console", "execution_mode": "manual"},
    )
    assert trigger.status_code == 202
    pipeline_id = trigger.json()["pipeline_id"]

    repository = get_pipeline_repository()
    repository.update_pipeline_metadata(
        UUID(pipeline_id),
        metadata_update={"waiting_for_stage": "plan"},
        status=PipelineStatus.SKIPPED,
        error_reason="awaiting_approval:plan",
    )

    resume = client.post(
        f"/api/v1/pipelines/{pipeline_id}/controls",
        json={"action": "resume"},
    )
    assert resume.status_code == 200
    assert resume.json()["action"] == "resume"
    assert resume.json()["status"] == PipelineStatus.QUEUED.value
    assert resume.json()["waiting_for_stage"] is None

    _reset_app_state()
