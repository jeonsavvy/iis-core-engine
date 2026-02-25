from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import get_pipeline_repository
from app.api.security import verify_internal_api_token
from app.schemas.pipeline import (
    PipelineControlAction,
    PipelineControlRequest,
    PipelineControlResponse,
    PipelineLogsResponse,
    PipelineStatus,
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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TriggerResponse:
    header_idempotency_key = idempotency_key.strip() if isinstance(idempotency_key, str) else None
    normalized_idempotency_key = (header_idempotency_key or payload.idempotency_key or "").strip() or None
    if normalized_idempotency_key and not (8 <= len(normalized_idempotency_key) <= 128):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="idempotency_key_invalid_length")

    request_payload = payload
    if normalized_idempotency_key != payload.idempotency_key:
        request_payload = payload.model_copy(update={"idempotency_key": normalized_idempotency_key})

    try:
        job = repository.create_pipeline(request_payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    request_id = job.metadata.get("request_id")
    return TriggerResponse(
        pipeline_id=job.pipeline_id,
        status=job.status,
        request_id=request_id if isinstance(request_id, str) and request_id else None,
    )


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


@router.post("/{pipeline_id}/controls", response_model=PipelineControlResponse)
def control_pipeline(
    pipeline_id: UUID,
    payload: PipelineControlRequest,
    repository: PipelineRepository = Depends(get_pipeline_repository),
) -> PipelineControlResponse:
    job = repository.get_pipeline(pipeline_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    if payload.action == PipelineControlAction.PAUSE:
        if job.status in {PipelineStatus.SUCCESS, PipelineStatus.ERROR}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="pause_status_not_allowed")
        updated = repository.update_pipeline_metadata(
            pipeline_id,
            metadata_update={"operator_control": {"pause_requested": True, "cancel_requested": False}},
            status=job.status,
            error_reason=job.error_reason,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
        return PipelineControlResponse(
            pipeline_id=updated.pipeline_id,
            action=payload.action,
            execution_mode=repository.get_execution_mode(updated),
            status=updated.status,
            waiting_for_stage=repository.get_waiting_for_stage(updated),
            error_reason=updated.error_reason,
        )

    if payload.action == PipelineControlAction.CANCEL:
        if job.status in {PipelineStatus.SUCCESS, PipelineStatus.ERROR}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cancel_status_not_allowed")
        if job.status in {PipelineStatus.QUEUED, PipelineStatus.SKIPPED}:
            updated = repository.update_pipeline_metadata(
                pipeline_id,
                metadata_update={
                    "operator_control": {"pause_requested": False, "cancel_requested": False},
                    "waiting_for_stage": None,
                },
                status=PipelineStatus.ERROR,
                error_reason="cancelled_by_operator",
            )
        else:
            updated = repository.update_pipeline_metadata(
                pipeline_id,
                metadata_update={"operator_control": {"pause_requested": False, "cancel_requested": True}},
                status=job.status,
                error_reason=job.error_reason,
            )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
        return PipelineControlResponse(
            pipeline_id=updated.pipeline_id,
            action=payload.action,
            execution_mode=repository.get_execution_mode(updated),
            status=updated.status,
            waiting_for_stage=repository.get_waiting_for_stage(updated),
            error_reason=updated.error_reason,
        )

    if payload.action == PipelineControlAction.RETRY:
        if job.status not in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="retry_status_not_allowed")
        updated = repository.update_pipeline_metadata(
            pipeline_id,
            metadata_update={
                "operator_control": {"pause_requested": False, "cancel_requested": False},
                "waiting_for_stage": None,
            },
            status=PipelineStatus.QUEUED,
            error_reason=None,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
        return PipelineControlResponse(
            pipeline_id=updated.pipeline_id,
            action=payload.action,
            execution_mode=repository.get_execution_mode(updated),
            status=updated.status,
            waiting_for_stage=repository.get_waiting_for_stage(updated),
            error_reason=updated.error_reason,
        )

    waiting_stage = repository.get_waiting_for_stage(job)
    if waiting_stage is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="resume_not_waiting_for_stage")

    try:
        approved = repository.approve_stage(pipeline_id, waiting_stage)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if approved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    updated = repository.update_pipeline_metadata(
        pipeline_id,
        metadata_update={"operator_control": {"pause_requested": False, "cancel_requested": False}},
        status=approved.status,
        error_reason=approved.error_reason,
    )
    final_job = updated or approved
    return PipelineControlResponse(
        pipeline_id=final_job.pipeline_id,
        action=payload.action,
        execution_mode=repository.get_execution_mode(final_job),
        status=final_job.status,
        waiting_for_stage=repository.get_waiting_for_stage(final_job),
        error_reason=final_job.error_reason,
    )
