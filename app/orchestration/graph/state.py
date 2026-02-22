from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from app.schemas.pipeline import PipelineLogRecord, PipelineStatus
from app.services.pipeline_repository import PipelineJob


class PipelineState(TypedDict):
    pipeline_id: UUID
    keyword: str
    qa_attempt: int
    max_qa_loops: int
    fail_qa_until: int
    build_iteration: int
    needs_rebuild: bool
    status: PipelineStatus
    reason: str | None
    logs: list[PipelineLogRecord]
    outputs: dict[str, Any]


def create_initial_state(job: PipelineJob) -> PipelineState:
    outputs: dict[str, Any] = {}
    safe_slug = job.metadata.get("safe_slug")
    if isinstance(safe_slug, str) and safe_slug:
        outputs["safe_slug"] = safe_slug
    pipeline_version = job.metadata.get("pipeline_version")
    if isinstance(pipeline_version, str) and pipeline_version:
        outputs["pipeline_version"] = pipeline_version

    return {
        "pipeline_id": job.pipeline_id,
        "keyword": job.keyword,
        "qa_attempt": 0,
        "max_qa_loops": 3,
        "fail_qa_until": job.qa_fail_until,
        "build_iteration": 0,
        "needs_rebuild": False,
        "status": PipelineStatus.RUNNING,
        "reason": None,
        "logs": [],
        "outputs": outputs,
    }
