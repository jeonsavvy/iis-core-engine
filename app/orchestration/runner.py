from __future__ import annotations

from app.core.config import Settings
from app.orchestration.graph.pipeline_graph import build_pipeline_graph
from app.orchestration.graph.state import PipelineState, create_initial_state
from app.orchestration.nodes import architect, builder, echo, publisher, qa_failed, sentinel, stylist, trigger
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import (
    ExecutionMode,
    PipelineAgentName,
    PipelineLogRecord,
    PipelineStage,
    PipelineStatus,
)
from app.services.github_service import GitHubArchiveService
from app.services.pipeline_repository import PipelineJob, PipelineRepository
from app.services.publisher_service import PublisherService
from app.services.quality_service import QualityService
from app.services.x_service import XService


class PipelineRunner:
    def __init__(
        self,
        *,
        repository: PipelineRepository,
        settings: Settings,
        x_service: XService | None = None,
        quality_service: QualityService | None = None,
        publisher_service: PublisherService | None = None,
        github_archive_service: GitHubArchiveService | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        deps = NodeDependencies(
            x_service=x_service or XService(settings),
            quality_service=quality_service or QualityService(settings),
            publisher_service=publisher_service or PublisherService(settings),
            github_archive_service=github_archive_service or GitHubArchiveService(settings),
        )
        self.deps = deps
        self.graph = build_pipeline_graph(deps)

    def run(self, job: PipelineJob) -> None:
        if self.repository.get_execution_mode(job) == ExecutionMode.MANUAL:
            self._run_manual(job)
            return

        state = create_initial_state(job)

        try:
            final_state = self.graph.invoke(state)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.repository.mark_pipeline_status(job.pipeline_id, PipelineStatus.ERROR, str(exc))
            return

        self.repository.append_logs(final_state["logs"])
        self.repository.mark_pipeline_status(
            job.pipeline_id,
            final_state["status"],
            error_reason=final_state.get("reason"),
        )

    def _run_manual(self, job: PipelineJob) -> None:
        state = create_initial_state(job)
        state["outputs"].update(self._manual_outputs(job))
        state["qa_attempt"] = self._manual_int(job, "manual_qa_attempt", state["qa_attempt"])
        state["build_iteration"] = self._manual_int(job, "manual_build_iteration", state["build_iteration"])
        state["status"] = PipelineStatus.RUNNING
        state["reason"] = None

        cursor = self._manual_cursor(job)

        try:
            if cursor == "trigger":
                state = trigger.run(state, self.deps)
                cursor = "plan"

            if cursor == "plan":
                if self._pause_if_unapproved(job, state, PipelineStage.PLAN):
                    self._finalize_manual_pause(job, state, cursor="plan")
                    return
                state = architect.run(state, self.deps)
                cursor = "style"

            if cursor == "style":
                if self._pause_if_unapproved(job, state, PipelineStage.STYLE):
                    self._finalize_manual_pause(job, state, cursor="style")
                    return
                state = stylist.run(state, self.deps)
                cursor = "build_qa"

            if cursor == "build_qa":
                if self._pause_if_unapproved(job, state, PipelineStage.BUILD):
                    self._finalize_manual_pause(job, state, cursor="build_qa")
                    return
                if self._pause_if_unapproved(job, state, PipelineStage.QA):
                    self._finalize_manual_pause(job, state, cursor="build_qa")
                    return

                while True:
                    state = builder.run(state, self.deps)
                    state = sentinel.run(state, self.deps)

                    if not state["needs_rebuild"]:
                        cursor = "publish"
                        break
                    if state["qa_attempt"] >= state["max_qa_loops"]:
                        state = qa_failed.run(state, self.deps)
                        cursor = "done"
                        break

            if cursor == "publish":
                if self._pause_if_unapproved(job, state, PipelineStage.PUBLISH):
                    self._finalize_manual_pause(job, state, cursor="publish")
                    return
                state = publisher.run(state, self.deps)
                if state["status"] == PipelineStatus.ERROR:
                    cursor = "done"
                else:
                    cursor = "echo"

            if cursor == "echo":
                if self._pause_if_unapproved(job, state, PipelineStage.ECHO):
                    self._finalize_manual_pause(job, state, cursor="echo")
                    return
                state = echo.run(state, self.deps)
                cursor = "done"

        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.repository.mark_pipeline_status(job.pipeline_id, PipelineStatus.ERROR, str(exc))
            return

        self.repository.append_logs(state["logs"])
        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update={
                "manual_cursor": cursor,
                "manual_outputs": state["outputs"],
                "manual_qa_attempt": state["qa_attempt"],
                "manual_build_iteration": state["build_iteration"],
                "waiting_for_stage": None,
            },
            status=state["status"],
            error_reason=state.get("reason"),
        )

    def _pause_if_unapproved(self, job: PipelineJob, state: PipelineState, stage: PipelineStage) -> bool:
        if self.repository.is_stage_approved(job, stage):
            return False

        state["status"] = PipelineStatus.SKIPPED
        state["reason"] = f"awaiting_approval:{stage.value}"
        state["logs"].append(
            PipelineLogRecord(
                pipeline_id=state["pipeline_id"],
                stage=stage,
                status=PipelineStatus.SKIPPED,
                agent_name=self._agent_for_stage(stage),
                message=f"Manual mode paused. Approve '{stage.value}' stage to continue.",
                reason=state["reason"],
                metadata={
                    "execution_mode": ExecutionMode.MANUAL.value,
                    "pipeline_version": str(state["outputs"].get("pipeline_version", self.settings.pipeline_default_version)),
                },
            )
        )
        return True

    def _finalize_manual_pause(self, job: PipelineJob, state: PipelineState, *, cursor: str) -> None:
        waiting_for_stage = self._waiting_stage_from_reason(state.get("reason"))
        self.repository.append_logs(state["logs"])
        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update={
                "manual_cursor": cursor,
                "manual_outputs": state["outputs"],
                "manual_qa_attempt": state["qa_attempt"],
                "manual_build_iteration": state["build_iteration"],
                "waiting_for_stage": waiting_for_stage.value if waiting_for_stage else None,
            },
            status=PipelineStatus.SKIPPED,
            error_reason=state.get("reason"),
        )

    @staticmethod
    def _waiting_stage_from_reason(reason: str | None) -> PipelineStage | None:
        if not reason or not reason.startswith("awaiting_approval:"):
            return None
        _, _, stage_value = reason.partition(":")
        try:
            return PipelineStage(stage_value)
        except ValueError:
            return None

    @staticmethod
    def _agent_for_stage(stage: PipelineStage) -> PipelineAgentName:
        mapping = {
            PipelineStage.PLAN: PipelineAgentName.ARCHITECT,
            PipelineStage.STYLE: PipelineAgentName.STYLIST,
            PipelineStage.BUILD: PipelineAgentName.BUILDER,
            PipelineStage.QA: PipelineAgentName.SENTINEL,
            PipelineStage.PUBLISH: PipelineAgentName.PUBLISHER,
            PipelineStage.ECHO: PipelineAgentName.ECHO,
        }
        return mapping.get(stage, PipelineAgentName.TRIGGER)

    @staticmethod
    def _manual_outputs(job: PipelineJob) -> dict[str, object]:
        value = job.metadata.get("manual_outputs")
        if isinstance(value, dict):
            return dict(value)
        return {}

    @staticmethod
    def _manual_int(job: PipelineJob, key: str, default: int) -> int:
        value = job.metadata.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return default

    @staticmethod
    def _manual_cursor(job: PipelineJob) -> str:
        value = job.metadata.get("manual_cursor")
        if not isinstance(value, str):
            return "trigger"
        if value not in {"trigger", "plan", "style", "build_qa", "publish", "echo", "done"}:
            return "trigger"
        return value
