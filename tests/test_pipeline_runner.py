from __future__ import annotations

from typing import Any, cast
from types import SimpleNamespace

from app.core.config import Settings
from app.orchestration.runner import PipelineRunner
from app.schemas.pipeline import PipelineStage, PipelineStatus, TriggerRequest
from app.services.pipeline_repository import PipelineRepository
from app.services.quality_service import ArtifactContractResult, GameplayGateResult, QualityGateResult, SmokeCheckResult


class FakeQualityService:
    def run_smoke_check(self, _html: str, **_kwargs) -> SmokeCheckResult:
        return SmokeCheckResult(
            ok=True,
            visual_metrics={
                "canvas_width": 1280.0,
                "canvas_height": 720.0,
                "luminance_std": 36.0,
                "non_dark_ratio": 0.32,
                "color_bucket_count": 34.0,
                "edge_energy": 0.052,
                "motion_delta": 0.0054,
            },
        )

    def evaluate_quality_contract(self, _html: str, *, design_spec=None, **_kwargs) -> QualityGateResult:
        return QualityGateResult(ok=True, score=90, threshold=75, failed_checks=[], checks={"quality": True})

    def evaluate_gameplay_gate(self, _html: str, *, design_spec=None, genre=None, **_kwargs) -> GameplayGateResult:
        return GameplayGateResult(ok=True, score=85, threshold=55, failed_checks=[], checks={"gameplay": True})

    def evaluate_visual_gate(self, _visual_metrics, *, genre_engine=None, **_kwargs) -> QualityGateResult:
        return QualityGateResult(ok=True, score=88, threshold=45, failed_checks=[], checks={"visual": True})

    def evaluate_artifact_contract(self, _artifact_manifest, *, art_direction_contract=None, **_kwargs) -> ArtifactContractResult:
        return ArtifactContractResult(
            ok=True,
            score=90,
            threshold=70,
            failed_checks=[],
            checks={"artifact_contract": True},
        )


class FakeLowQualityService(FakeQualityService):
    def __init__(self, *, hard_gate: bool = False) -> None:
        self.settings = SimpleNamespace(qa_hard_gate=hard_gate)

    def evaluate_quality_contract(self, _html: str, *, design_spec=None, **_kwargs) -> QualityGateResult:
        return QualityGateResult(
            ok=False,
            score=40,
            threshold=75,
            failed_checks=["viewport_meta"],
            checks={"viewport_meta": False},
        )


class FakePublisherService:
    def publish_game(
        self,
        *,
        slug: str,
        name: str,
        genre: str,
        html_content: str,
        artifact_files=None,
        entrypoint_path=None,
    ):
        assert slug
        assert name
        assert genre
        assert html_content
        assert artifact_files is None or isinstance(artifact_files, list)
        assert entrypoint_path is None or isinstance(entrypoint_path, str)
        return {
            "status": "published",
            "public_url": f"https://example.com/games/{slug}/index.html",
            "game_id": "fake-game-id",
        }

    def upload_screenshot(self, *, slug: str, screenshot_bytes: bytes) -> str:
        assert slug
        assert isinstance(screenshot_bytes, bytes)
        return f"https://example.com/screenshots/{slug}.png"

    def update_game_marketing(self, *, slug: str, ai_review: str, screenshot_url: str | None = None) -> dict[str, str]:
        assert slug
        assert ai_review
        if screenshot_url is not None:
            assert isinstance(screenshot_url, str)
        return {"status": "updated"}


class FakeGitHubArchiveService:
    def commit_archive_game(
        self,
        *,
        game_slug: str,
        game_name: str,
        genre: str,
        html_content: str,
        public_url: str,
        artifact_files=None,
    ):
        assert game_slug
        assert game_name
        assert genre
        assert html_content
        assert public_url
        assert artifact_files is None or isinstance(artifact_files, list)
        return {"status": "committed"}


def _make_runner(repository: PipelineRepository) -> PipelineRunner:
    settings = Settings(telegram_bot_token="")
    return PipelineRunner(
        repository=repository,
        settings=settings,
        quality_service=cast(Any, FakeQualityService()),
        publisher_service=cast(Any, FakePublisherService()),
        github_archive_service=cast(Any, FakeGitHubArchiveService()),
    )


def _make_runner_with_quality(repository: PipelineRepository, quality_service: Any) -> PipelineRunner:
    settings = Settings(telegram_bot_token="", builder_quality_floor_enforced=False)
    return PipelineRunner(
        repository=repository,
        settings=settings,
        quality_service=cast(Any, quality_service),
        publisher_service=cast(Any, FakePublisherService()),
        github_archive_service=cast(Any, FakeGitHubArchiveService()),
    )


def test_pipeline_runner_success_flow_contains_style_and_publish() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(TriggerRequest(keyword="arcade blast", qa_fail_until=0))
    queued_job = repository.claim_next_queued_pipeline()

    assert queued_job is not None

    runner = _make_runner(repository)
    runner.run(queued_job)

    final_job = repository.get_pipeline(job.pipeline_id)
    assert final_job is not None
    assert final_job.status == PipelineStatus.SUCCESS

    logs = repository.list_logs(job.pipeline_id)
    stages = [log.stage.value for log in logs]
    assert "design" in stages
    assert "release" in stages
    assert "report" in stages
    assert "done" in stages
    usage_summary = final_job.metadata.get("usage_summary")
    assert isinstance(usage_summary, dict)
    assert usage_summary.get("schema_version") == 2
    assert usage_summary.get("game_slug")


def test_pipeline_runner_forced_runtime_soft_fail_still_completes() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(TriggerRequest(keyword="retry test", qa_fail_until=3))
    queued_job = repository.claim_next_queued_pipeline()

    assert queued_job is not None

    runner = _make_runner(repository)
    runner.run(queued_job)

    final_job = repository.get_pipeline(job.pipeline_id)
    assert final_job is not None
    assert final_job.status == PipelineStatus.SUCCESS
    assert final_job.error_reason is None

    logs = repository.list_logs(job.pipeline_id)
    qa_runtime_logs = [log for log in logs if log.stage.value == "qa_runtime"]
    assert qa_runtime_logs
    assert any(log.reason == "soft_fail" for log in qa_runtime_logs)


def test_pipeline_runner_quality_gate_soft_fails_but_pipeline_succeeds() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(TriggerRequest(keyword="quality check", qa_fail_until=0))
    queued_job = repository.claim_next_queued_pipeline()

    assert queued_job is not None

    runner = _make_runner_with_quality(repository, FakeLowQualityService(hard_gate=False))
    runner.run(queued_job)

    final_job = repository.get_pipeline(job.pipeline_id)
    assert final_job is not None
    assert final_job.status == PipelineStatus.SUCCESS

    logs = repository.list_logs(job.pipeline_id)
    qa_quality_logs = [log for log in logs if log.stage == PipelineStage.QA_QUALITY]
    assert qa_quality_logs
    assert any(log.reason == "soft_fail" for log in qa_quality_logs)


def test_pipeline_runner_quality_gate_hard_gate_flag_does_not_block_release() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(TriggerRequest(keyword="quality hard gate", qa_fail_until=0))
    queued_job = repository.claim_next_queued_pipeline()

    assert queued_job is not None

    runner = _make_runner_with_quality(repository, FakeLowQualityService(hard_gate=True))
    runner.run(queued_job)

    final_job = repository.get_pipeline(job.pipeline_id)
    assert final_job is not None
    assert final_job.status == PipelineStatus.SUCCESS
    assert final_job.error_reason is None
