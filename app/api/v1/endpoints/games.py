from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.security import verify_internal_api_token
from app.core.config import get_settings
from app.schemas.games import DeleteGameRequest, DeleteGameResponse
from app.services.game_admin_service import GameAdminService

router = APIRouter(
    prefix="/games",
    tags=["games"],
    dependencies=[Depends(verify_internal_api_token)],
)


@router.delete("/{game_id}", response_model=DeleteGameResponse)
def delete_game(
    game_id: UUID,
    payload: DeleteGameRequest,
) -> DeleteGameResponse:
    service = GameAdminService(get_settings())
    result = service.delete_game(
        game_id=game_id,
        delete_storage=payload.delete_storage,
        delete_archive=payload.delete_archive,
        reason=payload.reason,
    )

    status_value = str(result.get("status"))
    if status_value == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result)
    if status_value == "error":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result)
    if status_value == "partial_error":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result)

    return DeleteGameResponse.model_validate(result)

