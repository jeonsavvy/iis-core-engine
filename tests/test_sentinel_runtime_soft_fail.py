from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.orchestration.nodes import qa_quality, sentinel
from app.schemas.pipeline import PipelineStatus
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult, SmokeCheckResult


class _RepoStub:
    def get_pipeline(self, _pipeline_id):
        return SimpleNamespace(metadata={})


class _RuntimeFailQualityService:
    def __init__(self, *, hard_gate: bool = False) -> None:
        self.settings = SimpleNamespace(qa_hard_gate=hard_gate)

    def run_smoke_check(self, *_args, **_kwargs):
        return SmokeCheckResult(
            ok=False,
            reason="runtime_console_error",
            fatal_errors=["NotAllowedError: play() failed"],
            non_fatal_warnings=["request_failed[image] file://sprite.png net::ERR_FILE_NOT_FOUND"],
            visual_metrics={
                "canvas_width": 1280.0,
                "canvas_height": 720.0,
                "luminance_std": 32.0,
                "non_dark_ratio": 0.45,
                "color_bucket_count": 36.0,
                "edge_energy": 0.05,
                "motion_delta": 0.002,
            },
        )

    def evaluate_quality_contract(self, *_args, **_kwargs):
        return QualityGateResult(ok=True, score=82, threshold=40, failed_checks=[], checks={"quality": True})

    def evaluate_gameplay_gate(self, *_args, **_kwargs):
        return GameplayGateResult(ok=True, score=80, threshold=55, failed_checks=[], checks={"gameplay": True})

    def evaluate_visual_gate(self, *_args, **_kwargs):
        return QualityGateResult(
            ok=False,
            score=24,
            threshold=45,
            failed_checks=["visual_palette_too_flat", "visual_shape_definition_too_low"],
            checks={"visual_palette_too_flat": False, "visual_shape_definition_too_low": False},
        )

    def evaluate_artifact_contract(self, *_args, **_kwargs):
        return ArtifactContractResult(ok=True, score=80, threshold=70, failed_checks=[], checks={"artifact": True})


class _RuntimeCriticalFailQualityService(_RuntimeFailQualityService):
    def run_smoke_check(self, *_args, **_kwargs):
        return SmokeCheckResult(
            ok=False,
            reason="runtime_console_error",
            fatal_errors=["immediate_game_over_visible_text", "immediate_zero_hp_state"],
            non_fatal_warnings=[],
            visual_metrics={
                "canvas_width": 1280.0,
                "canvas_height": 720.0,
                "luminance_std": 20.0,
                "non_dark_ratio": 0.21,
                "color_bucket_count": 18.0,
                "edge_energy": 0.021,
                "motion_delta": 0.0009,
            },
        )


class _PublisherStub:
    def upload_screenshot(self, **_kwargs):
        return None


def _base_state() -> dict[str, Any]:
    return {
        "pipeline_id": uuid4(),
        "keyword": "neon runner",
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
        "outputs": {
            "artifact_html": "<html><body><canvas id='game'></canvas></body></html>",
            "artifact_manifest": {"bundle_kind": "hybrid_engine"},
            "game_slug": "neon-runner",
            "game_genre": "arcade",
            "genre_engine": "arcade_generic",
        },
    }


def _deps_with_quality(quality_service) -> SimpleNamespace:
    return SimpleNamespace(
        repository=_RepoStub(),
        telegram_service=object(),
        quality_service=quality_service,
        publisher_service=_PublisherStub(),
        github_archive_service=object(),
        vertex_service=object(),
    )


def test_sentinel_runtime_failure_soft_fails_and_queues_improvement() -> None:
    state = _base_state()
    deps = _deps_with_quality(_RuntimeFailQualityService())

    result = sentinel.run(cast(Any, state), cast(Any, deps))

    assert result["needs_rebuild"] is False
    assert result["status"] == PipelineStatus.RUNNING
    assert any(log.status == PipelineStatus.SUCCESS for log in result["logs"])
    assert any("soft-fail" in log.message for log in result["logs"])

    improvement_items = result["outputs"].get("qa_improvement_items")
    assert isinstance(improvement_items, list)
    assert any(item.get("reason") == "runtime_console_error" for item in improvement_items if isinstance(item, dict))


def test_qa_quality_merges_runtime_and_quality_improvements() -> None:
    state = _base_state()
    deps = _deps_with_quality(_RuntimeFailQualityService())

    after_runtime = sentinel.run(cast(Any, state), cast(Any, deps))
    after_quality = qa_quality.run(cast(Any, after_runtime), cast(Any, deps))

    assert after_quality["status"] == PipelineStatus.RUNNING
    assert after_quality["needs_rebuild"] is False
    assert any(log.stage.value == "qa_quality" for log in after_quality["logs"])

    improvement_items = after_quality["outputs"].get("qa_improvement_items")
    assert isinstance(improvement_items, list)
    reasons = [item.get("reason") for item in improvement_items if isinstance(item, dict)]
    assert "runtime_console_error" in reasons
    assert "visual_quality_below_threshold" in reasons


def test_qa_quality_hard_gate_blocks_release_when_enabled() -> None:
    state = _base_state()
    deps = _deps_with_quality(_RuntimeFailQualityService(hard_gate=True))

    after_runtime = sentinel.run(cast(Any, state), cast(Any, deps))
    after_quality = qa_quality.run(cast(Any, after_runtime), cast(Any, deps))

    assert after_quality["status"] == PipelineStatus.ERROR
    assert after_quality["reason"] == "qa_hard_gate_blocked"
    assert any(log.status == PipelineStatus.ERROR and log.stage.value == "qa_quality" for log in after_quality["logs"])


def test_sentinel_runtime_critical_failure_requests_rebuild() -> None:
    state = _base_state()
    deps = _deps_with_quality(_RuntimeCriticalFailQualityService())

    result = sentinel.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.RUNNING
    assert result["needs_rebuild"] is True
    assert any(log.status == PipelineStatus.RETRY and log.reason == "retry_builder" for log in result["logs"])
