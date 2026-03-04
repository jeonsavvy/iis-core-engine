from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.orchestration.graph.state import create_initial_state
from app.schemas.pipeline import PipelineStatus, TriggerSource
from app.services.pipeline_repository import PipelineJob


def test_create_initial_state_loads_resume_metadata_outputs() -> None:
    pipeline_id = uuid4()
    now = datetime.now(timezone.utc)
    job = PipelineJob(
        pipeline_id=pipeline_id,
        keyword="resume test",
        source=TriggerSource.CONSOLE,
        status=PipelineStatus.QUEUED,
        requested_by=None,
        qa_fail_until=0,
        metadata={
            "safe_slug": "resume-test",
            "resume_stage": "build",
            "resume_outputs": {
                "analyze_contract": {"intent": "cached"},
                "plan_contract": {"core_mechanics": ["move"]},
            },
        },
        error_reason=None,
        created_at=now,
        updated_at=now,
    )

    state = create_initial_state(job)
    outputs = state["outputs"]
    assert outputs["resume_stage"] == "build"
    assert outputs["safe_slug"] == "resume-test"
    assert isinstance(outputs.get("analyze_contract"), dict)
    assert isinstance(outputs.get("plan_contract"), dict)
