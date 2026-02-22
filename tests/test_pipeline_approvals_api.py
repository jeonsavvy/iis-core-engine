from fastapi.testclient import TestClient

from app.api.deps import get_pipeline_repository
from app.core.config import get_settings
from app.main import app


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
