from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.orchestration.nodes import sentinel
from app.schemas.pipeline import PipelineStatus
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult, SmokeCheckResult


class _RepoStub:
    def get_pipeline(self, _pipeline_id):
        return SimpleNamespace(metadata={})


class _QualityServiceSoftFail:
    def run_smoke_check(self, *_args, **_kwargs):
        return SmokeCheckResult(
            ok=False,
            reason="runtime_console_error",
            fatal_errors=["NotAllowedError: play() failed"],
            non_fatal_warnings=[],
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
        return QualityGateResult(ok=True, score=78, threshold=45, failed_checks=[], checks={"visual": True})

    def evaluate_artifact_contract(self, *_args, **_kwargs):
        return ArtifactContractResult(ok=True, score=80, threshold=70, failed_checks=[], checks={"artifact": True})


class _PublisherStub:
    def upload_screenshot(self, **_kwargs):
        return None


def _base_state() -> dict:
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
            "builder_runtime_guard": {"chosen": "selected"},
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


def test_sentinel_tolerates_runtime_console_error_when_builder_guard_passed() -> None:
    state = _base_state()
    deps = _deps_with_quality(_QualityServiceSoftFail())

    result = sentinel.run(state, deps)

    assert result["needs_rebuild"] is False
    assert result["status"] == PipelineStatus.RUNNING
    assert any(log.status == PipelineStatus.SUCCESS for log in result["logs"])
    assert any("runtime console error tolerated" in log.message for log in result["logs"])


def test_sentinel_retries_runtime_console_error_without_builder_guard_context() -> None:
    state = _base_state()
    state["outputs"].pop("builder_runtime_guard", None)
    deps = _deps_with_quality(_QualityServiceSoftFail())

    result = sentinel.run(state, deps)

    assert result["needs_rebuild"] is True
    assert any(log.status == PipelineStatus.RETRY for log in result["logs"])
