from __future__ import annotations

from datetime import datetime, timezone

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineLogRecord, PipelineStage, PipelineStatus

_VERTEX_RESOURCE_EXHAUSTED_TOKENS: tuple[str, ...] = (
    "resource_exhausted",
    "resourceexhausted",
    "resource exhausted",
    "429",
    "quota",
    "rate limit",
    "too many requests",
)

_AGENT_LANE_BY_STAGE: dict[PipelineStage, str] = {
    PipelineStage.ANALYZE: "A",
    PipelineStage.PLAN: "A",
    PipelineStage.DESIGN: "A",
    PipelineStage.BUILD: "A",
    PipelineStage.QA_RUNTIME: "B",
    PipelineStage.QA_QUALITY: "B",
    PipelineStage.RELEASE: "B",
    PipelineStage.REPORT: "B",
    PipelineStage.DONE: "SYSTEM",
}

_HANDOFF_STAGE_BY_STAGE: dict[PipelineStage, PipelineStage] = {
    PipelineStage.ANALYZE: PipelineStage.PLAN,
    PipelineStage.PLAN: PipelineStage.DESIGN,
    PipelineStage.DESIGN: PipelineStage.BUILD,
    PipelineStage.BUILD: PipelineStage.QA_RUNTIME,
    PipelineStage.QA_RUNTIME: PipelineStage.QA_QUALITY,
    PipelineStage.QA_QUALITY: PipelineStage.RELEASE,
    PipelineStage.RELEASE: PipelineStage.REPORT,
}


def classify_vertex_unavailable_reason(
    *,
    default_reason: str,
    generation_meta: dict[str, object] | None,
) -> tuple[str, bool]:
    meta = generation_meta if isinstance(generation_meta, dict) else {}
    upstream_reason = str(meta.get("reason", "")).strip().casefold()
    vertex_error = str(meta.get("vertex_error", "")).strip().casefold()
    combined = f"{upstream_reason} {vertex_error}".strip()
    retryable = any(token in combined for token in _VERTEX_RESOURCE_EXHAUSTED_TOKENS)
    if retryable:
        return f"{default_reason}_vertex_resource_exhausted", True
    if upstream_reason == "vertex_not_configured":
        return f"{default_reason}_vertex_not_configured", False
    if upstream_reason.startswith("vertex_error:"):
        return f"{default_reason}_vertex_error", False
    return default_reason, False


def append_log(
    state: PipelineState,
    *,
    stage: PipelineStage,
    status: PipelineStatus,
    agent_name: PipelineAgentName,
    message: str,
    reason: str | None = None,
    metadata: dict | None = None,
) -> PipelineState:
    metadata_payload = dict(metadata or {})
    if "agent_lane" not in metadata_payload:
        metadata_payload["agent_lane"] = _AGENT_LANE_BY_STAGE.get(stage, "SYSTEM")
    if "handoff_to_stage" not in metadata_payload and status == PipelineStatus.SUCCESS:
        handoff_stage = _HANDOFF_STAGE_BY_STAGE.get(stage)
        if handoff_stage is not None:
            metadata_payload["handoff_to_stage"] = handoff_stage.value
    if "handoff_summary" not in metadata_payload:
        compact_message = " ".join(message.split()).strip()
        if compact_message:
            metadata_payload["handoff_summary"] = compact_message[:200]

    record = PipelineLogRecord(
        pipeline_id=state["pipeline_id"],
        stage=stage,
        status=status,
        agent_name=agent_name,
        message=message,
        reason=reason,
        attempt=state["qa_attempt"] if state["qa_attempt"] > 0 else 1,
        metadata=metadata_payload,
        created_at=datetime.now(timezone.utc),
    )
    state["logs"].append(record)

    log_sink = state.get("log_sink")
    if callable(log_sink):
        try:
            log_sink(record)
            state["flushed_log_count"] = state.get("flushed_log_count", 0) + 1
        except Exception:
            # Runtime logging sink failures should not crash the pipeline execution path.
            pass
    return state


def apply_operator_control_gate(
    state: PipelineState,
    deps: NodeDependencies,
    *,
    stage: PipelineStage,
    agent_name: PipelineAgentName,
    allow_pause: bool = True,
) -> PipelineState | None:
    job = deps.repository.get_pipeline(state["pipeline_id"])
    if job is None:
        return None

    raw_control = job.metadata.get("operator_control")
    control = raw_control if isinstance(raw_control, dict) else {}
    cancel_requested = bool(control.get("cancel_requested"))
    pause_requested = bool(control.get("pause_requested")) if allow_pause else False

    if cancel_requested:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "cancelled_by_operator"
        state["needs_rebuild"] = False
        return append_log(
            state,
            stage=stage,
            status=PipelineStatus.ERROR,
            agent_name=agent_name,
            message=f"Pipeline cancelled by operator before '{stage.value}' stage execution.",
            reason=state["reason"],
            metadata={"operator_control": control, "guard_stage": stage.value},
        )

    if pause_requested:
        state["status"] = PipelineStatus.SKIPPED
        state["reason"] = "paused_by_operator"
        state["needs_rebuild"] = False
        return append_log(
            state,
            stage=stage,
            status=PipelineStatus.SKIPPED,
            agent_name=agent_name,
            message=f"Pipeline paused by operator before '{stage.value}' stage execution.",
            reason=state["reason"],
            metadata={"operator_control": control, "guard_stage": stage.value},
        )

    return None
