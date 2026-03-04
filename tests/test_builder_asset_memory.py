from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.orchestration.nodes.builder_parts.asset_memory import collect_asset_memory_context
from app.schemas.pipeline import PipelineAgentName, PipelineLogRecord, PipelineStage, PipelineStatus


class _FakeRepository:
    def __init__(self, logs: list[PipelineLogRecord], registry_rows: list[dict] | None = None) -> None:
        self._logs = logs
        self._registry_rows = registry_rows or []

    def list_recent_logs(self, limit: int = 100) -> list[PipelineLogRecord]:
        return self._logs[:limit]

    def list_asset_registry(self, *, core_loop_type: str, limit: int = 80) -> list[dict]:
        filtered = [row for row in self._registry_rows if row.get("core_loop_type") == core_loop_type]
        return filtered[:limit]


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
        agent_name=PipelineAgentName.DEVELOPER if stage == PipelineStage.BUILD else PipelineAgentName.QA_RUNTIME,
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
            stage=PipelineStage.QA_RUNTIME,
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
    deps = cast(Any, SimpleNamespace(repository=_FakeRepository(logs)))

    result = collect_asset_memory_context(
        state=cast(Any, _state(current_pipeline_id)),
        deps=deps,
        core_loop_type="webgl_three_runner",
    )

    profile = result.retrieval_profile
    failure_reasons = cast(list[str], profile.get("failure_reasons", []))
    failure_tokens = cast(list[str], profile.get("failure_tokens", []))
    assert profile.get("preferred_asset_pack") == "webgl_neon_highway"
    assert profile.get("preferred_variant_id") == "clarity-first"
    assert profile.get("preferred_variant_theme") == "readability"
    assert "visual_quality_below_threshold" in failure_reasons
    assert "contrast" in failure_tokens
    assert "diversity" in failure_tokens
    assert result.hint
    assert "Reuse proven asset pack webgl_neon_highway." in result.hint


def test_collect_asset_memory_context_prefers_registry_when_present() -> None:
    current_pipeline_id = uuid4()
    deps = cast(
        Any,
        SimpleNamespace(
            repository=_FakeRepository(
                logs=[],
                registry_rows=[
                {
                    "pipeline_id": str(uuid4()),
                    "core_loop_type": "webgl_three_runner",
                    "asset_pack": "webgl_neon_highway",
                    "variant_id": "clarity-first",
                    "variant_theme": "readability",
                    "final_composite_score": 95.6,
                    "failure_reasons": ["visual_quality_below_threshold"],
                    "failure_tokens": ["contrast"],
                }
            ],
        )
        ),
    )

    result = collect_asset_memory_context(
        state=cast(Any, _state(current_pipeline_id)),
        deps=deps,
        core_loop_type="webgl_three_runner",
    )

    assert result.retrieval_profile.get("source") == "asset_registry_v1"
    assert result.retrieval_profile.get("preferred_asset_pack") == "webgl_neon_highway"
    assert "visual_quality_below_threshold" in cast(list[str], result.retrieval_profile.get("failure_reasons", []))


def test_collect_asset_memory_context_reads_build_blocking_reasons_as_feedback() -> None:
    current_pipeline_id = uuid4()
    pipeline_a = uuid4()
    logs = [
        _log(
            pipeline_id=pipeline_a,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            metadata={"core_loop_type": "flight_sim_3d"},
            offset_seconds=1,
        ),
        _log(
            pipeline_id=pipeline_a,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            reason="builder_quality_floor_unmet",
            metadata={
                "blocking_reasons": ["quality_gate_unmet", "intent_mechanics_unmet"],
                "quality_floor_fail_reasons": ["visual_gate_unmet"],
            },
            offset_seconds=2,
        ),
    ]
    deps = cast(Any, SimpleNamespace(repository=_FakeRepository(logs)))

    result = collect_asset_memory_context(
        state=cast(Any, _state(current_pipeline_id)),
        deps=deps,
        core_loop_type="flight_sim_3d",
    )

    reasons = cast(list[str], result.retrieval_profile.get("failure_reasons", []))
    tokens = cast(list[str], result.retrieval_profile.get("failure_tokens", []))
    assert "builder_quality_floor_unmet" in reasons
    assert "intent_mechanics_unmet" in tokens


def test_collect_asset_memory_context_registry_scoring_penalizes_failed_rows() -> None:
    current_pipeline_id = uuid4()
    deps = cast(
        Any,
        SimpleNamespace(
            repository=_FakeRepository(
                logs=[],
                registry_rows=[
                {
                    "pipeline_id": str(uuid4()),
                    "keyword": "generic speed game",
                    "core_loop_type": "webgl_three_runner",
                    "asset_pack": "failed_pack",
                    "variant_id": "failed-variant",
                    "variant_theme": "aggressive",
                    "final_composite_score": 99.0,
                    "qa_status": "error",
                    "failure_reasons": ["runtime_error_detected"],
                    "failure_tokens": ["console_error"],
                },
                {
                    "pipeline_id": str(uuid4()),
                    "keyword": "neon racer sprint",
                    "core_loop_type": "webgl_three_runner",
                    "asset_pack": "stable_pack",
                    "variant_id": "clarity-first",
                    "variant_theme": "readability",
                    "final_composite_score": 88.0,
                    "qa_status": "success",
                    "failure_reasons": [],
                    "failure_tokens": [],
                },
            ],
        )
        ),
    )

    result = collect_asset_memory_context(
        state=cast(Any, _state(current_pipeline_id)),
        deps=deps,
        core_loop_type="webgl_three_runner",
    )

    assert result.retrieval_profile.get("preferred_asset_pack") == "stable_pack"
    assert result.retrieval_profile.get("preferred_variant_id") == "clarity-first"
    assert cast(int, result.retrieval_profile.get("keyword_match_count", 0)) >= 1
