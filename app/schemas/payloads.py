from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GDDPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    genre: str = Field(min_length=1, max_length=40)
    objective: str = Field(min_length=1, max_length=300)
    visual_style: str | None = Field(default=None, max_length=80)


class AnalyzeContractPayload(BaseModel):
    intent: str = Field(min_length=1, max_length=200)
    scope_in: list[str] = Field(default_factory=list, max_length=10)
    scope_out: list[str] = Field(default_factory=list, max_length=10)
    hard_constraints: list[str] = Field(default_factory=list, max_length=10)
    forbidden_patterns: list[str] = Field(default_factory=list, max_length=12)
    success_outcome: str = Field(min_length=1, max_length=240)


class PlanContractPayload(BaseModel):
    core_mechanics: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    progression_plan: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    encounter_plan: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    risk_reward_plan: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    control_model: str = Field(min_length=1, max_length=120)
    balance_baseline: dict[str, float] = Field(default_factory=dict)


class DesignContractPayload(BaseModel):
    camera_ui_contract: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    asset_blueprint_2d3d: list[str] = Field(default_factory=list, min_length=1, max_length=18)
    scene_layers: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    feedback_fx_contract: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    readability_contract: list[str] = Field(default_factory=list, min_length=1, max_length=12)


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
    class ArtifactFile(BaseModel):
        path: str = Field(pattern=r"^games\/[^\/]+\/[A-Za-z0-9._-]+$")
        content: str = Field(min_length=1)
        content_type: str = Field(min_length=3, max_length=120)

    game_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    game_name: str = Field(min_length=1, max_length=120)
    game_genre: str = Field(min_length=1, max_length=40)
    artifact_path: str = Field(pattern=r"^games\/[^\/]+\/index\.html$")
    artifact_html: str = Field(min_length=50)
    entrypoint_path: str | None = Field(default=None, pattern=r"^games\/[^\/]+\/index\.html$")
    artifact_files: list[ArtifactFile] | None = None
    artifact_manifest: dict[str, object] | None = None
    leaderboard_contract: LeaderboardContract = Field(default_factory=LeaderboardContract)

    @model_validator(mode="after")
    def ensure_bundle_defaults(self) -> "BuildArtifactPayload":
        if self.entrypoint_path is None:
            self.entrypoint_path = self.artifact_path
        if self.artifact_files is None:
            self.artifact_files = [
                BuildArtifactPayload.ArtifactFile(
                    path=self.artifact_path,
                    content=self.artifact_html,
                    content_type="text/html; charset=utf-8",
                )
            ]
        return self
