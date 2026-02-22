from app.core.config import Settings
from app.schemas.pipeline import ExecutionMode, PipelineStage, PipelineStatus, TriggerRequest
from app.services.pipeline_repository import PipelineRepository


def test_create_pipeline_normalizes_keyword_and_sets_safe_slug() -> None:
    repository = PipelineRepository(settings=Settings())

    job = repository.create_pipeline(TriggerRequest(keyword="  Neon   Arena  "))

    assert job.keyword == "Neon Arena"
    assert job.metadata["safe_slug"] == "neon-arena"


def test_create_pipeline_blocks_forbidden_keyword() -> None:
    repository = PipelineRepository(settings=Settings(trigger_forbidden_keywords="secret"))

    try:
        repository.create_pipeline(TriggerRequest(keyword="secret run"))
    except ValueError as exc:
        assert str(exc) == "keyword_contains_blocked_term"
        return

    raise AssertionError("expected ValueError")


def test_approve_stage_sets_pipeline_back_to_queued() -> None:
    repository = PipelineRepository(settings=Settings())
    created = repository.create_pipeline(
        TriggerRequest(
            keyword="manual approval",
            execution_mode=ExecutionMode.MANUAL,
        )
    )

    repository.update_pipeline_metadata(
        created.pipeline_id,
        metadata_update={"waiting_for_stage": "plan"},
        status=PipelineStatus.SKIPPED,
        error_reason="awaiting_approval:plan",
    )

    approved = repository.approve_stage(created.pipeline_id, PipelineStage.PLAN)
    assert approved is not None
    assert approved.status == PipelineStatus.QUEUED
    assert approved.error_reason is None
    assert "plan" in approved.metadata["approved_stages"]
