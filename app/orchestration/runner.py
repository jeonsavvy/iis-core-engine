from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

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
        status = final_state["status"]
        error_reason = final_state.get("reason")
        failure_snapshot = self._build_failure_snapshot(final_state=final_state, error_reason=error_reason)
        metadata_update: dict[str, object] = {
            "execution_mode": "auto",
            "usage_summary": usage_summary,
            "operator_control": {"pause_requested": False, "cancel_requested": False},
            "failure_snapshot": failure_snapshot,
        }

        if status == PipelineStatus.RETRY:
            retry_plan = self._build_vertex_retry_plan(job=job, final_state=final_state)
            metadata_update["vertex_retry"] = retry_plan["vertex_retry"]
            metadata_update["retry_not_before_at"] = retry_plan["retry_not_before_at"]
            retry_status_raw = retry_plan.get("status")
            if isinstance(retry_status_raw, PipelineStatus):
                retry_status = retry_status_raw
            else:
                retry_status = PipelineStatus.ERROR
            resume_payload = self._build_resume_payload(status=retry_status, final_state=final_state)
            metadata_update.update(resume_payload)
            status = retry_status
            error_reason = retry_plan["error_reason"]
        else:
            metadata_update["vertex_retry"] = {
                "attempt": 0,
                "not_before_at": None,
                "last_reason": None,
                "last_stage": None,
            }
            metadata_update["retry_not_before_at"] = None
            metadata_update["resume_stage"] = None
            metadata_update["resume_outputs"] = {}

        self.repository.update_pipeline_metadata(
            job.pipeline_id,
            metadata_update=metadata_update,
            status=status,
            error_reason=error_reason,
        )
        self._emit_failure_report_if_needed(
            job=job,
            status=status,
            error_reason=error_reason,
            failure_snapshot=failure_snapshot,
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

    def _build_vertex_retry_plan(self, *, job: PipelineJob, final_state: PipelineState) -> dict[str, object]:
        retry_meta_raw = job.metadata.get("vertex_retry")
        retry_meta = retry_meta_raw if isinstance(retry_meta_raw, dict) else {}
        previous_attempt = self._coerce_non_negative_int(retry_meta.get("attempt", 0))
        attempt = previous_attempt + 1
        max_attempts = int(self.settings.vertex_retry_max_attempts_per_pipeline)
        reason = str(final_state.get("reason") or "vertex_resource_exhausted").strip() or "vertex_resource_exhausted"
        last_stage = final_state["logs"][-1].stage.value if final_state["logs"] else None

        if attempt > max_attempts:
            exhausted_reason = f"{reason}_retry_exhausted"
            return {
                "status": PipelineStatus.ERROR,
                "error_reason": exhausted_reason,
                "retry_not_before_at": None,
                "vertex_retry": {
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "not_before_at": None,
                    "last_reason": exhausted_reason,
                    "last_stage": last_stage,
                    "state": "exhausted",
                },
            }

        base = max(1, int(self.settings.vertex_retry_backoff_base_seconds))
        delay_seconds = min(
            int(self.settings.vertex_retry_backoff_max_seconds),
            base * (2 ** max(0, attempt - 1)),
        )
        jitter = max(0, int(self.settings.vertex_retry_jitter_seconds))
        if jitter > 0:
            delay_seconds += int(job.pipeline_id.int % (jitter + 1))

        retry_not_before = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        retry_not_before_at = retry_not_before.isoformat()
        return {
            "status": PipelineStatus.QUEUED,
            "error_reason": reason,
            "retry_not_before_at": retry_not_before_at,
            "vertex_retry": {
                "attempt": attempt,
                "max_attempts": max_attempts,
                "delay_seconds": delay_seconds,
                "not_before_at": retry_not_before_at,
                "last_reason": reason,
                "last_stage": last_stage,
                "state": "scheduled",
            },
        }

    def _build_resume_payload(self, *, status: PipelineStatus, final_state: PipelineState) -> dict[str, object]:
        if status != PipelineStatus.QUEUED:
            return {"resume_stage": None, "resume_outputs": {}}
        reason = str(final_state.get("reason") or "").strip().casefold()
        if reason != "build_vertex_resource_exhausted":
            return {"resume_stage": None, "resume_outputs": {}}
        outputs = final_state.get("outputs", {})
        if not isinstance(outputs, dict):
            return {"resume_stage": None, "resume_outputs": {}}
        snapshot_keys = (
            "safe_slug",
            "pipeline_version",
            "analyze_contract",
            "analyze_contract_source",
            "analyze_contract_meta",
            "research_summary",
            "gdd",
            "gdd_source",
            "gdd_meta",
            "plan_contract",
            "plan_contract_source",
            "plan_contract_meta",
            "design_spec",
            "design_spec_source",
            "design_spec_meta",
            "design_contract",
            "design_contract_source",
            "design_contract_meta",
            "art_direction_contract",
            "intent_contract",
            "intent_contract_hash",
            "synapse_contract",
            "synapse_contract_hash",
            "shared_generation_contract",
            "shared_generation_contract_hash",
        )
        resume_outputs: dict[str, Any] = {}
        for key in snapshot_keys:
            value = outputs.get(key)
            if value is None:
                continue
            resume_outputs[key] = value
        if not resume_outputs:
            return {"resume_stage": None, "resume_outputs": {}}
        return {
            "resume_stage": "build",
            "resume_outputs": resume_outputs,
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

    @staticmethod
    def _normalize_reason(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        token = value.strip()
        if not token:
            return None
        known_prefixes = ("visual:", "runtime:", "intent:", "gameplay:", "quality:", "codegen:", "other:")
        while True:
            lowered = token.casefold()
            matched = False
            for prefix in known_prefixes:
                if lowered.startswith(prefix):
                    token = token[len(prefix) :].strip()
                    matched = True
                    break
            if not matched:
                break
        return token.casefold()

    @staticmethod
    def _dedupe_reasons(rows: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for row in rows:
            if row in seen:
                continue
            seen.add(row)
            deduped.append(row)
        return deduped

    @classmethod
    def _collect_log_reasons(cls, metadata: dict[str, Any], reason: str | None) -> list[str]:
        rows: list[str] = []
        primary = cls._normalize_reason(reason)
        if primary:
            rows.append(primary)

        for key in ("blocking_reasons", "quality_floor_fail_reasons", "blocking_reasons_normalized"):
            value = metadata.get(key)
            if not isinstance(value, list):
                continue
            for item in value:
                normalized = cls._normalize_reason(item)
                if normalized:
                    rows.append(normalized)

        intent_gate = metadata.get("intent_gate_report")
        if isinstance(intent_gate, dict):
            failed_items = intent_gate.get("failed_items")
            if isinstance(failed_items, list):
                for item in failed_items:
                    normalized = cls._normalize_reason(item)
                    if normalized:
                        rows.append(normalized)

        return cls._dedupe_reasons(rows)

    @staticmethod
    def _classify_reason(reason: str) -> str:
        if reason.startswith("checklist:"):
            checklist = reason[len("checklist:") :]
            if (
                checklist.startswith("visual_")
                or checklist.startswith("color_")
                or "contrast" in checklist
                or "diversity" in checklist
                or "edge" in checklist
                or "motion" in checklist
                or "composition" in checklist
            ):
                return "visual"
            if (
                checklist.startswith("input_")
                or checklist.startswith("state_")
                or checklist.startswith("restart_")
                or checklist.startswith("runtime_")
            ):
                return "runtime"
            if checklist.startswith("gameplay_") or checklist.startswith("core_loop") or checklist.startswith("progression"):
                return "gameplay"
            return "quality"
        if reason.startswith("intent:") or reason.startswith("intent_") or reason == "intent_gate_unmet":
            return "intent"
        if reason.startswith("codegen_") or reason.startswith("codegen:") or reason.startswith("codegen_reason:") or reason.startswith("codegen_error:"):
            return "codegen"
        if reason.startswith("runtime_") or reason in {
            "runtime_smoke_failed",
            "builder_playability_unmet",
            "input_reactivity_missing",
            "missing_realtime_loop",
            "restart_loop",
            "core_loop_tick",
        }:
            return "runtime"
        if reason.startswith("visual_") or reason in {
            "visual_gate_unmet",
            "visual_contrast",
            "color_diversity",
            "edge_definition",
            "motion_presence",
            "composition_balance",
            "visual_cohesion",
        }:
            return "visual"
        if reason.startswith("gameplay_") or reason == "gameplay_gate_unmet":
            return "gameplay"
        if reason.startswith("quality_") or reason in {"quality_gate_unmet", "generation_checklist_unmet"}:
            return "quality"
        if reason in {
            "builder_quality_floor_unmet",
            "gdd_unavailable",
            "design_spec_unavailable",
            "plan_contract_invalid",
        }:
            return "system"
        return "other"

    @classmethod
    def _build_failure_snapshot(
        cls,
        *,
        final_state: PipelineState,
        error_reason: object,
    ) -> dict[str, Any] | None:
        status = final_state.get("status")
        if status not in {PipelineStatus.ERROR, PipelineStatus.RETRY, PipelineStatus.SKIPPED}:
            return None

        all_reasons: list[str] = []
        stage_failure_map: dict[str, list[str]] = {}
        latest_error_stage: str | None = None
        latest_error_message: str | None = None

        for log in final_state.get("logs", []):
            metadata = log.metadata if isinstance(log.metadata, dict) else {}
            reasons = cls._collect_log_reasons(metadata, log.reason)
            if reasons and log.status in {PipelineStatus.ERROR, PipelineStatus.RETRY}:
                stage_key = log.stage.value
                previous = stage_failure_map.get(stage_key, [])
                stage_failure_map[stage_key] = cls._dedupe_reasons([*previous, *reasons])
                latest_error_stage = stage_key
                latest_error_message = str(log.message or "").strip() or None
            all_reasons.extend(reasons)

        deduped_reasons = cls._dedupe_reasons(all_reasons)
        normalized_error_reason = cls._normalize_reason(error_reason)
        primary = normalized_error_reason or (deduped_reasons[0] if deduped_reasons else None)
        secondary = [row for row in deduped_reasons if row != primary][:8]

        reason_groups: dict[str, list[str]] = {}
        grouped_input = [primary, *secondary] if primary else secondary
        for reason in grouped_input:
            if not reason:
                continue
            category = cls._classify_reason(reason)
            reason_groups.setdefault(category, [])
            if reason not in reason_groups[category]:
                reason_groups[category].append(reason)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status.value if isinstance(status, PipelineStatus) else str(status),
            "primary_failure_reason": primary,
            "secondary_reasons": secondary,
            "failure_reason_groups": reason_groups,
            "stage_failure_map": stage_failure_map,
            "latest_error_stage": latest_error_stage,
            "latest_error_message": latest_error_message,
        }

    def _emit_failure_report_if_needed(
        self,
        *,
        job: PipelineJob,
        status: PipelineStatus,
        error_reason: object,
        failure_snapshot: dict[str, Any] | None,
    ) -> None:
        if status != PipelineStatus.ERROR:
            return
        if not self.settings.telegram_failure_report_broadcast:
            return
        summary = failure_snapshot if isinstance(failure_snapshot, dict) else {}
        primary = str(summary.get("primary_failure_reason") or self._normalize_reason(error_reason) or "unknown_error")
        secondary = summary.get("secondary_reasons")
        secondary_rows = secondary if isinstance(secondary, list) else []
        secondary_text = ", ".join(str(row) for row in secondary_rows[:3]) if secondary_rows else "-"
        latest_stage = str(summary.get("latest_error_stage") or "-")
        message = "\n".join(
            [
                "🚨 파이프라인 실패 자동 보고",
                f"pipeline={job.pipeline_id}",
                f"keyword={job.keyword}",
                f"primary={primary}",
                f"secondary={secondary_text}",
                f"stage={latest_stage}",
            ]
        )
        try:
            self.deps.telegram_service.broadcast_message(message)
        except Exception:
            return
