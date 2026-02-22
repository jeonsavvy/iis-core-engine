from __future__ import annotations

from datetime import datetime, timezone

from app.orchestration.graph.state import PipelineState
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
