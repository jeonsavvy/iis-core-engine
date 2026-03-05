from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TriggerSource(str, Enum):
    TELEGRAM = "telegram"
    CONSOLE = "console"


class ExecutionMode(str, Enum):
    AUTO = "auto"


class AppRole(str, Enum):
    MASTER_ADMIN = "master_admin"
    REVIEWER = "reviewer"


class PipelineStage(str, Enum):
    ANALYZE = "analyze"
    PLAN = "plan"
    DESIGN = "design"
    BUILD = "build"
    QA_RUNTIME = "qa_runtime"
    QA_QUALITY = "qa_quality"
    RELEASE = "release"
    REPORT = "report"
    DONE = "done"


class PipelineStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    RETRY = "retry"
    SKIPPED = "skipped"


class PipelineControlAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    RETRY = "retry"


class PipelineAgentName(str, Enum):
    ANALYZER = "analyzer"
    PLANNER = "planner"
    DESIGNER = "designer"
    DEVELOPER = "developer"
    QA_RUNTIME = "qa_runtime"
    QA_QUALITY = "qa_quality"
    RELEASER = "releaser"
    REPORTER = "reporter"


class TriggerRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    requested_by: UUID | None = None
    source: TriggerSource = TriggerSource.CONSOLE
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    pipeline_version: str = Field(default="forgeflow-v1", min_length=1, max_length=40)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    qa_fail_until: int = Field(default=0, ge=0, le=3)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriggerResponse(BaseModel):
    pipeline_id: UUID
    status: PipelineStatus
    request_id: str | None = None


class PipelineSummary(BaseModel):
    pipeline_id: UUID
    keyword: str
    source: TriggerSource
    status: PipelineStatus
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    pipeline_version: str = "forgeflow-v1"
    error_reason: str | None = None
    failure_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class StageApprovalRequest(BaseModel):
    stage: PipelineStage


class StageApprovalResponse(BaseModel):
    pipeline_id: UUID
    approved_stage: PipelineStage
    execution_mode: ExecutionMode
    status: PipelineStatus


class PipelineControlRequest(BaseModel):
    action: PipelineControlAction


class PipelineControlResponse(BaseModel):
    pipeline_id: UUID
    action: PipelineControlAction
    execution_mode: ExecutionMode
    status: PipelineStatus
    error_reason: str | None = None


class PipelineLogRecord(BaseModel):
    pipeline_id: UUID
    stage: PipelineStage
    status: PipelineStatus
    agent_name: PipelineAgentName
    message: str
    reason: str | None = None
    attempt: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineLogsResponse(BaseModel):
    pipeline_id: UUID
    logs: list[PipelineLogRecord]
