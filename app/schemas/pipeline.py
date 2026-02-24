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
    MANUAL = "manual"


class AppRole(str, Enum):
    MASTER_ADMIN = "master_admin"
    REVIEWER = "reviewer"


class PipelineStage(str, Enum):
    TRIGGER = "trigger"
    PLAN = "plan"
    STYLE = "style"
    BUILD = "build"
    QA = "qa"
    PUBLISH = "publish"
    ECHO = "echo"
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
    TRIGGER = "Trigger"
    ARCHITECT = "Architect"
    STYLIST = "Stylist"
    BUILDER = "Builder"
    SENTINEL = "Sentinel"
    PUBLISHER = "Publisher"
    ECHO = "Echo"


class TriggerRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    requested_by: UUID | None = None
    source: TriggerSource = TriggerSource.CONSOLE
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    pipeline_version: str = Field(default="forgeflow-v1", min_length=1, max_length=40)
    qa_fail_until: int = Field(default=0, ge=0, le=3)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriggerResponse(BaseModel):
    pipeline_id: UUID
    status: PipelineStatus


class PipelineSummary(BaseModel):
    pipeline_id: UUID
    keyword: str
    source: TriggerSource
    status: PipelineStatus
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    waiting_for_stage: PipelineStage | None = None
    pipeline_version: str = "forgeflow-v1"
    error_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StageApprovalRequest(BaseModel):
    stage: PipelineStage


class StageApprovalResponse(BaseModel):
    pipeline_id: UUID
    approved_stage: PipelineStage
    execution_mode: ExecutionMode
    status: PipelineStatus
    waiting_for_stage: PipelineStage | None = None


class PipelineControlRequest(BaseModel):
    action: PipelineControlAction


class PipelineControlResponse(BaseModel):
    pipeline_id: UUID
    action: PipelineControlAction
    execution_mode: ExecutionMode
    status: PipelineStatus
    waiting_for_stage: PipelineStage | None = None
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
