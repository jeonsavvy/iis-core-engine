from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GDDPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    genre: str = Field(min_length=1, max_length=40)
    objective: str = Field(min_length=1, max_length=300)
    visual_style: str | None = Field(default=None, max_length=80)


class DesignSpecPayload(BaseModel):
    visual_style: str = Field(min_length=1, max_length=80)
    palette: list[str] = Field(min_length=1, max_length=8)
    hud: str = Field(min_length=1, max_length=120)
    viewport_width: int = Field(default=1280, ge=640, le=1920)
    viewport_height: int = Field(default=720, ge=360, le=1080)
    safe_area_padding: int = Field(default=24, ge=0, le=64)
    min_font_size_px: int = Field(default=14, ge=10, le=24)
    text_overflow_policy: str = Field(default="ellipsis-clamp", min_length=3, max_length=40)
    typography: str | None = Field(default=None, max_length=80)
    thumbnail_concept: str | None = Field(default=None, max_length=200)


class LeaderboardContract(BaseModel):
    endpoint_env_var: str = "__IIS_LEADERBOARD_ENDPOINT"
    anon_key_env_var: str = "__IIS_SUPABASE_ANON_KEY"
    game_id_env_var: str = "__IIS_GAME_ID"
    method: Literal["POST"] = "POST"


class BuildArtifactPayload(BaseModel):
    game_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    game_name: str = Field(min_length=1, max_length=120)
    game_genre: str = Field(min_length=1, max_length=40)
    artifact_path: str = Field(pattern=r"^games\/[^\/]+\/index\.html$")
    artifact_html: str = Field(min_length=50)
    leaderboard_contract: LeaderboardContract = Field(default_factory=LeaderboardContract)
