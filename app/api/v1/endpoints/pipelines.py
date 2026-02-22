from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_pipeline_repository
from app.api.security import verify_internal_api_token
from app.schemas.pipeline import (
    PipelineLogsResponse,
    PipelineSummary,
    StageApprovalRequest,
    StageApprovalResponse,
    TriggerRequest,
    TriggerResponse,
)
from app.services.pipeline_repository import PipelineRepository

router = APIRouter(
    prefix="/pipelines",
    tags=["pipelines"],
    dependencies=[Depends(verify_internal_api_token)],
)


@router.post("/trigger", response_model=TriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline(
    payload: TriggerRequest,
    repository: PipelineRepository = Depends(get_pipeline_repository),
) -> TriggerResponse:
    try:
        job = repository.create_pipeline(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return TriggerResponse(pipeline_id=job.pipeline_id, status=job.status)


@router.get("/{pipeline_id}", response_model=PipelineSummary)
def get_pipeline(
    pipeline_id: UUID,
    repository: PipelineRepository = Depends(get_pipeline_repository),
) -> PipelineSummary:
    job = repository.get_pipeline(pipeline_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    return PipelineSummary(
        pipeline_id=job.pipeline_id,
        keyword=job.keyword,
        source=job.source,
        status=job.status,
        execution_mode=repository.get_execution_mode(job),
        waiting_for_stage=repository.get_waiting_for_stage(job),
        pipeline_version=repository.get_pipeline_version(job),
        error_reason=job.error_reason,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{pipeline_id}/logs", response_model=PipelineLogsResponse)
def get_pipeline_logs(
    pipeline_id: UUID,
    repository: PipelineRepository = Depends(get_pipeline_repository),
) -> PipelineLogsResponse:
    job = repository.get_pipeline(pipeline_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    logs = repository.list_logs(pipeline_id)
    return PipelineLogsResponse(pipeline_id=pipeline_id, logs=logs)


@router.post("/{pipeline_id}/approvals", response_model=StageApprovalResponse)
def approve_pipeline_stage(
    pipeline_id: UUID,
    payload: StageApprovalRequest,
    repository: PipelineRepository = Depends(get_pipeline_repository),
) -> StageApprovalResponse:
    try:
        updated_job = repository.approve_stage(pipeline_id, payload.stage)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if updated_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    return StageApprovalResponse(
        pipeline_id=updated_job.pipeline_id,
        approved_stage=payload.stage,
        execution_mode=repository.get_execution_mode(updated_job),
        status=updated_job.status,
        waiting_for_stage=repository.get_waiting_for_stage(updated_job),
    )
