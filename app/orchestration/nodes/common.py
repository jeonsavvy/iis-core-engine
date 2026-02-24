from __future__ import annotations

from datetime import datetime, timezone

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineLogRecord, PipelineStage, PipelineStatus


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
    record = PipelineLogRecord(
        pipeline_id=state["pipeline_id"],
        stage=stage,
        status=status,
        agent_name=agent_name,
        message=message,
        reason=reason,
        attempt=state["qa_attempt"] if state["qa_attempt"] > 0 else 1,
        metadata=metadata or {},
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
        state["reason"] = f"awaiting_approval:{stage.value}"
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
