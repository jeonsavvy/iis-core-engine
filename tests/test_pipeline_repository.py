from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.schemas.pipeline import PipelineAgentName, PipelineStage, TriggerRequest
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


def test_approve_stage_raises_removed_error() -> None:
    repository = PipelineRepository(settings=Settings())
    created = repository.create_pipeline(
        TriggerRequest(
            keyword="approval removed",
        )
    )
    try:
        repository.approve_stage(created.pipeline_id, PipelineStage.PLAN)
    except ValueError as exc:
        assert str(exc) == "approval_api_removed"
    else:
        raise AssertionError("expected ValueError for removed approval API")


def test_create_pipeline_reuses_job_for_same_idempotency_key() -> None:
    repository = PipelineRepository(settings=Settings())
    request = TriggerRequest(keyword="neon arena", idempotency_key="idem-key-0001")

    first = repository.create_pipeline(request)
    second = repository.create_pipeline(request)

    assert first.pipeline_id == second.pipeline_id
    assert first.metadata.get("idempotency_key") == "idem-key-0001"
    assert first.metadata.get("request_id") == second.metadata.get("request_id")


def test_asset_registry_in_memory_upsert_and_list() -> None:
    repository = PipelineRepository(settings=Settings())
    job = repository.create_pipeline(TriggerRequest(keyword="asset memory sample"))

    repository.upsert_asset_registry_entry(
        {
            "pipeline_id": str(job.pipeline_id),
            "game_slug": "asset-memory-sample",
            "game_name": "Asset Memory Sample",
            "keyword": "asset memory sample",
            "core_loop_type": "webgl_three_runner",
            "asset_pack": "webgl_neon_highway",
            "variant_id": "clarity-first",
            "variant_theme": "readability",
            "final_composite_score": 91.4,
            "failure_reasons": ["visual_quality_below_threshold"],
            "failure_tokens": ["contrast"],
        }
    )

    rows = repository.list_asset_registry(core_loop_type="webgl_three_runner", limit=10)
    assert len(rows) == 1
    assert rows[0]["asset_pack"] == "webgl_neon_highway"
    assert rows[0]["variant_id"] == "clarity-first"


def test_log_from_row_normalizes_legacy_stage_and_agent_name() -> None:
    row: dict[str, Any] = {
        "pipeline_id": str(uuid4()),
        "stage": "echo",
        "status": "success",
        "agent_name": "Echo",
        "message": "legacy log",
        "reason": None,
        "attempt": 1,
        "metadata": {},
        "created_at": "2026-03-01T00:00:00Z",
    }

    parsed = PipelineRepository._log_from_row(row)

    assert parsed.stage == PipelineStage.REPORT
    assert parsed.agent_name == PipelineAgentName.REPORTER


def test_log_from_row_falls_back_agent_by_stage_when_unknown() -> None:
    row: dict[str, Any] = {
        "pipeline_id": str(uuid4()),
        "stage": "build",
        "status": "running",
        "agent_name": "unknown-agent",
        "message": "legacy log",
        "reason": None,
        "attempt": 1,
        "metadata": {},
        "created_at": "2026-03-01T00:00:00Z",
    }

    parsed = PipelineRepository._log_from_row(row)

    assert parsed.stage == PipelineStage.BUILD
    assert parsed.agent_name == PipelineAgentName.DEVELOPER
