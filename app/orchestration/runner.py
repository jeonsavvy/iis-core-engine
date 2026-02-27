from __future__ import annotations

from datetime import datetime, timezone

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
from app.services.telegram_service import TelegramService
from app.services.vertex_service import VertexService


class PipelineRunner:
    def __init__(
        self,
        *,
        repository: PipelineRepository,
        settings: Settings,
        telegram_service: TelegramService | None = None,
        quality_service: QualityService | None = None,
        publisher_service: PublisherService | None = None,
        github_archive_service: GitHubArchiveService | None = None,
        vertex_service: VertexService | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        deps = NodeDependencies(
            repository=repository,
            telegram_service=telegram_service or TelegramService(settings),
            quality_service=quality_service or QualityService(settings),
            publisher_service=publisher_service or PublisherService(settings),
            github_archive_service=github_archive_service or GitHubArchiveService(settings),
            vertex_service=vertex_service or VertexService(settings),
        )
        self.deps = deps
        self.graph = build_pipeline_graph(deps)

    def run(self, job: PipelineJob) -> None:
        if self.repository.get_execution_mode(job) == ExecutionMode.MANUAL:
            self._run_manual(job)
            return

        state = create_initial_state(job, log_sink=self._log_sink)

        try:
            final_state = self.graph.invoke(state)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.repository.mark_pipeline_status(job.pipeline_id, PipelineStatus.ERROR, str(exc))
            return

        self._flush_pending_logs(final_state)
        usage_summary = self._build_usage_summary(final_state)
        metadata_update: dict[str, object] = {
            "usage_summary": usage_summary,
            "operator_control": {"pause_requested": False, "cancel_requested": False},
        }
        waiting_for_stage = self._waiting_stage_from_reason(final_state.get("reason"))
        if final_state["status"] == PipelineStatus.SKIPPED and waiting_for_stage is not None:
            metadata_update.update(
                {
                    "execution_mode": ExecutionMode.MANUAL.value,
                    "manual_cursor": self._cursor_for_pause_stage(waiting_for_stage),
                    "manual_outputs": final_state["outputs"],
                    "manual_qa_attempt": final_state["qa_attempt"],
                    "manual_build_iteration": final_state["build_iteration"],
                    "waiting_for_stage": waiting_for_stage.value,
                }
            )
        elif final_state.get("reason") == "cancelled_by_operator":
            metadata_update["waiting_for_stage"] = None

        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update=metadata_update,
            status=final_state["status"],
            error_reason=final_state.get("reason"),
        )

    def _run_manual(self, job: PipelineJob) -> None:
        state = create_initial_state(job, log_sink=self._log_sink)
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
                    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
                        cursor = "done" if state["status"] == PipelineStatus.ERROR else "build_qa"
                        break
                    state = sentinel.run(state, self.deps)
                    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
                        cursor = "done" if state["status"] == PipelineStatus.ERROR else "build_qa"
                        break

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

        if state["status"] == PipelineStatus.SKIPPED and self._waiting_stage_from_reason(state.get("reason")) is not None:
            self._finalize_manual_pause(job, state, cursor=cursor)
            return

        self._flush_pending_logs(state)
        usage_summary = self._build_usage_summary(state)
        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update={
                "manual_cursor": cursor,
                "manual_outputs": state["outputs"],
                "manual_qa_attempt": state["qa_attempt"],
                "manual_build_iteration": state["build_iteration"],
                "waiting_for_stage": None,
                "usage_summary": usage_summary,
                "operator_control": {"pause_requested": False, "cancel_requested": False},
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
        self._flush_pending_logs(state)
        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update={
                "manual_cursor": cursor,
                "manual_outputs": state["outputs"],
                "manual_qa_attempt": state["qa_attempt"],
                "manual_build_iteration": state["build_iteration"],
                "waiting_for_stage": waiting_for_stage.value if waiting_for_stage else None,
                "operator_control": {"pause_requested": False, "cancel_requested": False},
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
    def _cursor_for_pause_stage(stage: PipelineStage) -> str:
        mapping = {
            PipelineStage.TRIGGER: "trigger",
            PipelineStage.PLAN: "plan",
            PipelineStage.STYLE: "style",
            PipelineStage.BUILD: "build_qa",
            PipelineStage.QA: "build_qa",
            PipelineStage.PUBLISH: "publish",
            PipelineStage.ECHO: "echo",
        }
        return mapping.get(stage, "trigger")

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

    def _log_sink(self, log: PipelineLogRecord) -> None:
        self.repository.append_logs([log])

    def _flush_pending_logs(self, state: PipelineState) -> None:
        flushed_count = int(state.get("flushed_log_count", 0))
        pending = state["logs"][flushed_count:]
        if pending:
            self.repository.append_logs(pending)
            state["flushed_log_count"] = len(state["logs"])

    def _build_usage_summary(self, state: PipelineState) -> dict[str, object]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        estimated_cost_usd = 0.0
        usage_log_count = 0
        model_breakdown: dict[str, dict[str, float]] = {}
        unpriced_tokens = 0

        for log in state["logs"]:
            usage = log.metadata.get("usage")
            if not isinstance(usage, dict):
                continue

            prompt = self._coerce_non_negative_int(usage.get("prompt_tokens", 0))
            completion = self._coerce_non_negative_int(usage.get("completion_tokens", 0))
            total = self._coerce_non_negative_int(usage.get("total_tokens", 0)) or (prompt + completion)
            if prompt <= 0 and completion <= 0 and total <= 0:
                continue

            usage_log_count += 1
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total

            model_name = str(log.metadata.get("model", "")).strip().lower()
            model_cost = self._estimate_usage_cost(model_name, prompt, completion)
            estimated_cost_usd += model_cost

            if model_name:
                row = model_breakdown.setdefault(
                    model_name,
                    {
                        "prompt_tokens": 0.0,
                        "completion_tokens": 0.0,
                        "total_tokens": 0.0,
                        "estimated_cost_usd": 0.0,
                    },
                )
                row["prompt_tokens"] += prompt
                row["completion_tokens"] += completion
                row["total_tokens"] += total
                row["estimated_cost_usd"] += model_cost
            else:
                unpriced_tokens += total

        game_slug = state["outputs"].get("game_slug")
        game_slug_value = str(game_slug) if isinstance(game_slug, str) else None
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "game_slug": game_slug_value,
            "usage_log_count": usage_log_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost_usd, 6),
            "unpriced_tokens": unpriced_tokens,
            "model_breakdown": model_breakdown,
        }

    @staticmethod
    def _estimate_usage_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        if "flash" in model_name:
            return (prompt_tokens / 1_000_000) * 0.075 + (completion_tokens / 1_000_000) * 0.3
        if "pro" in model_name:
            return (prompt_tokens / 1_000_000) * 1.25 + (completion_tokens / 1_000_000) * 5.0
        return 0.0

    @staticmethod
    def _coerce_non_negative_int(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if not isinstance(value, (int, float, str)):
            return 0
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0
        return parsed if parsed > 0 else 0
