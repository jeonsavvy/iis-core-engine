from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.payloads import (
    AnalyzeContractPayload,
    DesignContractPayload,
    DesignSpecPayload,
    GDDPayload,
    PlanContractPayload,
)


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


class GDDModel(GDDPayload):
    research_intent: str = Field(min_length=1, max_length=240)
    references: list[str] = Field(default_factory=list, max_length=8)


AnalyzeContractModel = AnalyzeContractPayload
PlanContractModel = PlanContractPayload
DesignContractModel = DesignContractPayload
DesignSpecModel = DesignSpecPayload
