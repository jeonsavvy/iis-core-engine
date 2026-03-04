from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.schemas.pipeline import PipelineStatus, TriggerRequest
from app.services.pipeline_repository import PipelineRepository


def test_requeue_stale_running_pipeline_in_memory() -> None:
    repository = PipelineRepository()
    created = repository.create_pipeline(TriggerRequest(keyword="stale check"))

    running = repository.claim_next_queued_pipeline()
    assert running is not None
    assert running.status == PipelineStatus.RUNNING

    memory_row = repository._memory_jobs[str(running.pipeline_id)]  # noqa: SLF001
    memory_row["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

    requeued = repository.requeue_stale_running_pipelines(max_age_seconds=60)
    assert requeued == 1

    refreshed = repository.get_pipeline(created.pipeline_id)
    assert refreshed is not None
    assert refreshed.status == PipelineStatus.QUEUED
    assert refreshed.error_reason == "requeued_stale_running"


def test_do_not_requeue_recent_running_pipeline() -> None:
    repository = PipelineRepository()
    created = repository.create_pipeline(TriggerRequest(keyword="fresh check"))

    running = repository.claim_next_queued_pipeline()
    assert running is not None

    requeued = repository.requeue_stale_running_pipelines(max_age_seconds=3600)
    assert requeued == 0

    refreshed = repository.get_pipeline(created.pipeline_id)
    assert refreshed is not None
    assert refreshed.status == PipelineStatus.RUNNING


def test_requeued_job_can_be_claimed_again() -> None:
    repository = PipelineRepository()
    created = repository.create_pipeline(TriggerRequest(keyword="claim again"))

    running = repository.claim_next_queued_pipeline()
    assert running is not None

    memory_row = repository._memory_jobs[str(running.pipeline_id)]  # noqa: SLF001
    memory_row["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    repository.requeue_stale_running_pipelines(max_age_seconds=60)
    reclaimed = repository.claim_next_queued_pipeline()

    assert reclaimed is not None
    assert reclaimed.pipeline_id == UUID(str(created.pipeline_id))
    assert reclaimed.status == PipelineStatus.RUNNING


def test_claim_next_queued_pipeline_respects_retry_not_before() -> None:
    repository = PipelineRepository()
    created = repository.create_pipeline(TriggerRequest(keyword="retry schedule"))
    job_id = str(created.pipeline_id)

    memory_row = repository._memory_jobs[job_id]  # noqa: SLF001
    memory_row["payload"]["vertex_retry"] = {
        "attempt": 1,
        "not_before_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
    }

    claimed = repository.claim_next_queued_pipeline()
    assert claimed is None

    memory_row["payload"]["vertex_retry"]["not_before_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    claimed_after = repository.claim_next_queued_pipeline()
    assert claimed_after is not None
    assert claimed_after.pipeline_id == UUID(job_id)
