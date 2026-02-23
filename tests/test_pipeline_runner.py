from __future__ import annotations

from app.core.config import Settings
from app.orchestration.runner import PipelineRunner
from app.schemas.pipeline import ExecutionMode, PipelineStage, PipelineStatus, TriggerRequest
from app.services.pipeline_repository import PipelineRepository
from app.services.quality_service import GameplayGateResult, QualityGateResult, SmokeCheckResult


class FakeQualityService:
    def run_smoke_check(self, _html: str) -> SmokeCheckResult:
        return SmokeCheckResult(ok=True)

    def evaluate_quality_contract(self, _html: str, *, design_spec=None) -> QualityGateResult:
        return QualityGateResult(ok=True, score=90, threshold=75, failed_checks=[], checks={"quality": True})

    def evaluate_gameplay_gate(self, _html: str, *, design_spec=None, genre=None) -> GameplayGateResult:
        return GameplayGateResult(ok=True, score=85, threshold=55, failed_checks=[], checks={"gameplay": True})


class FakeLowQualityService(FakeQualityService):
    def evaluate_quality_contract(self, _html: str, *, design_spec=None) -> QualityGateResult:
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

    def upload_screenshot(self, *, slug: str, screenshot_png: bytes) -> dict[str, str]:
        assert slug
        assert isinstance(screenshot_png, bytes)
        return {"status": "uploaded", "screenshot_url": f"https://example.com/screenshots/{slug}.png"}

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
        quality_service=FakeQualityService(),
        publisher_service=FakePublisherService(),
        github_archive_service=FakeGitHubArchiveService(),
    )


def _make_runner_with_quality(repository: PipelineRepository, quality_service) -> PipelineRunner:
    settings = Settings(telegram_bot_token="")
    return PipelineRunner(
        repository=repository,
        settings=settings,
        quality_service=quality_service,
        publisher_service=FakePublisherService(),
        github_archive_service=FakeGitHubArchiveService(),
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
    assert "style" in stages
    assert "publish" in stages
    assert "done" in stages
    usage_summary = final_job.metadata.get("usage_summary")
    assert isinstance(usage_summary, dict)
    assert usage_summary.get("schema_version") == 1
    assert usage_summary.get("game_slug")


def test_pipeline_runner_marks_error_after_three_qa_retries() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(TriggerRequest(keyword="retry test", qa_fail_until=3))
    queued_job = repository.claim_next_queued_pipeline()

    assert queued_job is not None

    runner = _make_runner(repository)
    runner.run(queued_job)

    final_job = repository.get_pipeline(job.pipeline_id)
    assert final_job is not None
    assert final_job.status == PipelineStatus.ERROR
    assert final_job.error_reason == "QA failed after 3 attempts"

    logs = repository.list_logs(job.pipeline_id)
    qa_retry_logs = [log for log in logs if log.stage.value == "qa" and log.status.value == "retry"]
    assert len(qa_retry_logs) == 3
    assert any(log.status.value == "error" and log.stage.value == "qa" for log in logs)


def test_pipeline_runner_quality_gate_can_fail_pipeline() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(TriggerRequest(keyword="quality check", qa_fail_until=0))
    queued_job = repository.claim_next_queued_pipeline()

    assert queued_job is not None

    runner = _make_runner_with_quality(repository, FakeLowQualityService())
    runner.run(queued_job)

    final_job = repository.get_pipeline(job.pipeline_id)
    assert final_job is not None
    assert final_job.status == PipelineStatus.ERROR
    assert final_job.error_reason == "QA failed after 3 attempts"

    logs = repository.list_logs(job.pipeline_id)
    quality_failures = [
        log
        for log in logs
        if log.stage == PipelineStage.QA and log.reason == "quality_score_below_threshold"
    ]
    assert len(quality_failures) == 3


def test_manual_mode_pauses_and_resumes_with_stage_approval() -> None:
    repository = PipelineRepository()
    job = repository.create_pipeline(
        TriggerRequest(
            keyword="manual mode",
            execution_mode=ExecutionMode.MANUAL,
        )
    )

    first_claim = repository.claim_next_queued_pipeline()
    assert first_claim is not None

    runner = _make_runner(repository)
    runner.run(first_claim)

    paused = repository.get_pipeline(job.pipeline_id)
    assert paused is not None
    assert paused.status == PipelineStatus.SKIPPED
    assert paused.error_reason == "awaiting_approval:plan"
    assert paused.metadata["waiting_for_stage"] == "plan"

    repository.approve_stage(job.pipeline_id, PipelineStage.PLAN)
    second_claim = repository.claim_next_queued_pipeline()
    assert second_claim is not None

    runner.run(second_claim)

    paused_again = repository.get_pipeline(job.pipeline_id)
    assert paused_again is not None
    assert paused_again.status == PipelineStatus.SKIPPED
    assert paused_again.error_reason == "awaiting_approval:style"

    repository.approve_stage(job.pipeline_id, PipelineStage.STYLE)
    third_claim = repository.claim_next_queued_pipeline()
    assert third_claim is not None

    runner.run(third_claim)

    paused_build = repository.get_pipeline(job.pipeline_id)
    assert paused_build is not None
    assert paused_build.status == PipelineStatus.SKIPPED
    assert paused_build.error_reason == "awaiting_approval:build"
