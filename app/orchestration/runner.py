from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import Settings
from app.orchestration.graph.pipeline_graph import build_pipeline_graph
from app.orchestration.graph.state import PipelineState, create_initial_state
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineLogRecord, PipelineStatus
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
        state = create_initial_state(job, log_sink=self._log_sink)

        try:
            final_state = self.graph.invoke(state)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.repository.mark_pipeline_status(job.pipeline_id, PipelineStatus.ERROR, str(exc))
            return

        self._flush_pending_logs(final_state)
        usage_summary = self._build_usage_summary(final_state)
        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update={
                "execution_mode": "auto",
                "usage_summary": usage_summary,
                "operator_control": {"pause_requested": False, "cancel_requested": False},
            },
            status=final_state["status"],
            error_reason=final_state.get("reason"),
        )

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
            "schema_version": 2,
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
