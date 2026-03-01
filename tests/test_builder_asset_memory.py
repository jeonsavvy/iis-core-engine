from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.orchestration.nodes.builder_parts.asset_memory import collect_asset_memory_context
from app.schemas.pipeline import PipelineAgentName, PipelineLogRecord, PipelineStage, PipelineStatus


class _FakeRepository:
    def __init__(self, logs: list[PipelineLogRecord]) -> None:
        self._logs = logs

    def list_recent_logs(self, limit: int = 100) -> list[PipelineLogRecord]:
        return self._logs[:limit]


def _log(
    *,
    pipeline_id,
    stage: PipelineStage,
    status: PipelineStatus,
    reason: str | None = None,
    metadata: dict | None = None,
    offset_seconds: int = 0,
) -> PipelineLogRecord:
    return PipelineLogRecord(
        pipeline_id=pipeline_id,
        stage=stage,
        status=status,
        agent_name=PipelineAgentName.BUILDER if stage == PipelineStage.BUILD else PipelineAgentName.SENTINEL,
        message="test",
        reason=reason,
        metadata=metadata or {},
        created_at=datetime.now(timezone.utc) - timedelta(seconds=offset_seconds),
    )


def _state(pipeline_id):
    return {
        "pipeline_id": pipeline_id,
        "keyword": "neon racer",
        "qa_attempt": 0,
        "max_qa_loops": 3,
        "fail_qa_until": 0,
        "build_iteration": 1,
        "needs_rebuild": False,
        "status": PipelineStatus.RUNNING,
        "reason": None,
        "logs": [],
        "flushed_log_count": 0,
        "log_sink": None,
        "outputs": {},
    }


def test_collect_asset_memory_context_reads_recent_build_and_failure_signals() -> None:
    current_pipeline_id = uuid4()
    pipeline_a = uuid4()
    pipeline_b = uuid4()
    pipeline_other = uuid4()

    logs = [
        _log(
            pipeline_id=pipeline_a,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            metadata={"core_loop_type": "webgl_three_runner"},
            offset_seconds=1,
        ),
        _log(
            pipeline_id=pipeline_a,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.SUCCESS,
            metadata={
                "asset_pack": "webgl_neon_highway",
                "final_composite_score": 92.1,
                "asset_pipeline_selected_variant": "clarity-first",
                "asset_pipeline_selected_theme": "readability",
            },
            offset_seconds=2,
        ),
        _log(
            pipeline_id=pipeline_a,
            stage=PipelineStage.QA,
            status=PipelineStatus.RETRY,
            reason="visual_quality_below_threshold",
            metadata={"failed_checks": ["contrast", "color_diversity"]},
            offset_seconds=3,
        ),
        _log(
            pipeline_id=pipeline_b,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            metadata={"core_loop_type": "webgl_three_runner"},
            offset_seconds=4,
        ),
        _log(
            pipeline_id=pipeline_b,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.SUCCESS,
            metadata={
                "asset_pack": "neon_arcade",
                "final_composite_score": 81.2,
                "asset_pipeline_selected_variant": "aggressive-arcade",
                "asset_pipeline_selected_theme": "aggressive",
            },
            offset_seconds=5,
        ),
        _log(
            pipeline_id=pipeline_other,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            metadata={"core_loop_type": "topdown_roguelike_shooter"},
            offset_seconds=6,
        ),
        _log(
            pipeline_id=pipeline_other,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.SUCCESS,
            metadata={"asset_pack": "fantasy_topdown", "final_composite_score": 99.0},
            offset_seconds=7,
        ),
    ]
    deps = SimpleNamespace(repository=_FakeRepository(logs))

    result = collect_asset_memory_context(
        state=_state(current_pipeline_id),
        deps=deps,
        core_loop_type="webgl_three_runner",
    )

    profile = result.retrieval_profile
    assert profile.get("preferred_asset_pack") == "webgl_neon_highway"
    assert profile.get("preferred_variant_id") == "clarity-first"
    assert profile.get("preferred_variant_theme") == "readability"
    assert "visual_quality_below_threshold" in profile.get("failure_reasons", [])
    assert "contrast" in profile.get("failure_tokens", [])
    assert result.hint
    assert "Reuse proven asset pack webgl_neon_highway." in result.hint
