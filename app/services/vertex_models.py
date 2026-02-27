from __future__ import annotations

from pydantic import BaseModel, Field


class GameConfigModel(BaseModel):
    player_hp: int = 3
    player_speed: int = 240
    player_attack_cooldown: float = 0.5
    enemy_hp: int = 1
    enemy_speed_min: int = 100
    enemy_speed_max: int = 220
    enemy_spawn_rate: float = 1.0
    time_limit_sec: int = 60
    base_score_value: int = 10


class GDDModel(BaseModel):
    title: str
    genre: str
    objective: str
    visual_style: str = "neon-minimal"
    research_intent: str
    references: list[str] = Field(default_factory=list)


class DesignSpecModel(BaseModel):
    visual_style: str
    palette: list[str]
    hud: str
    viewport_width: int = 1280
    viewport_height: int = 720
    safe_area_padding: int = 24
    min_font_size_px: int = 14
    text_overflow_policy: str = "ellipsis-clamp"
    typography: str = "inter-bold-hud"
    thumbnail_concept: str = "High-contrast action scene"
