from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DeleteGameRequest(BaseModel):
    delete_storage: bool = True
    delete_archive: bool = True
    reason: str = Field(default="admin_manual_delete", min_length=1, max_length=120)


class DeleteGameResponse(BaseModel):
    status: str
    game_id: UUID
    slug: str
    deleted: dict[str, bool]
    details: dict[str, Any] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class RepairPresentationRequest(BaseModel):
    rebroadcast_telegram: bool = False
    require_thumbnail: bool = True


class RepairPresentationResponse(BaseModel):
    status: str
    game_id: UUID
    slug: str
    visibility: str
    thumbnail_url: str | None = None
    telegram: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
