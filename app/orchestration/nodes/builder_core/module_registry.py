from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeModule:
    module_id: str
    layer: str
    version: str
    capability_tags: tuple[str, ...]
    stability_score: float
    description: str


_MODULES: dict[str, RuntimeModule] = {
    "scene_world": RuntimeModule(
        module_id="scene_world",
        layer="world",
        version="1.0.0",
        capability_tags=("render:2d", "render:3d", "world"),
        stability_score=0.92,
        description="월드/스폰 영역을 구성합니다.",
    ),
    "camera_stack": RuntimeModule(
        module_id="camera_stack",
        layer="camera",
        version="1.0.0",
        capability_tags=("camera", "render"),
        stability_score=0.91,
        description="카메라 투영과 시점 효과를 담당합니다.",
    ),
    "controller_stack": RuntimeModule(
        module_id="controller_stack",
        layer="control",
        version="1.0.0",
        capability_tags=("input", "movement"),
        stability_score=0.94,
        description="입력축과 이동 모델을 처리합니다.",
    ),
    "combat_stack": RuntimeModule(
        module_id="combat_stack",
        layer="combat",
        version="1.0.0",
        capability_tags=("combat",),
        stability_score=0.9,
        description="근접/원거리 전투 루프를 처리합니다.",
    ),
    "progression_stack": RuntimeModule(
        module_id="progression_stack",
        layer="progression",
        version="1.0.0",
        capability_tags=("progression",),
        stability_score=0.9,
        description="목표/보상/다음 목표 루프를 처리합니다.",
    ),
    "feedback_stack": RuntimeModule(
        module_id="feedback_stack",
        layer="feedback",
        version="1.0.0",
        capability_tags=("fx", "audio", "ui"),
        stability_score=0.93,
        description="시각/오디오/상태 피드백을 제공합니다.",
    ),
    "hud_stack": RuntimeModule(
        module_id="hud_stack",
        layer="hud",
        version="1.0.0",
        capability_tags=("hud",),
        stability_score=0.97,
        description="플레이어 중심 HUD를 렌더링합니다.",
    ),
    "flight_physics": RuntimeModule(
        module_id="flight_physics",
        layer="movement",
        version="1.0.0",
        capability_tags=("flight",),
        stability_score=0.87,
        description="비행 동역학 보강 모듈.",
    ),
    "vehicle_dynamics": RuntimeModule(
        module_id="vehicle_dynamics",
        layer="movement",
        version="1.0.0",
        capability_tags=("vehicle",),
        stability_score=0.89,
        description="차량 조향/관성 보강 모듈.",
    ),
    "projectile_system": RuntimeModule(
        module_id="projectile_system",
        layer="combat",
        version="1.0.0",
        capability_tags=("ranged",),
        stability_score=0.9,
        description="원거리 투사체 시스템 모듈.",
    ),
    "combo_chain": RuntimeModule(
        module_id="combo_chain",
        layer="combat",
        version="1.0.0",
        capability_tags=("melee",),
        stability_score=0.88,
        description="근접 콤보 체인 보강 모듈.",
    ),
    "checkpoint_loop": RuntimeModule(
        module_id="checkpoint_loop",
        layer="progression",
        version="1.0.0",
        capability_tags=("checkpoint",),
        stability_score=0.9,
        description="체크포인트 진행 루프 보강 모듈.",
    ),
    "camera_fx": RuntimeModule(
        module_id="camera_fx",
        layer="camera",
        version="1.0.0",
        capability_tags=("camera", "fx"),
        stability_score=0.91,
        description="카메라 쉐이크/줌 등 연출 모듈.",
    ),
}


def get_runtime_module(module_id: str) -> RuntimeModule | None:
    return _MODULES.get(module_id)


def list_runtime_modules(module_ids: list[str]) -> list[RuntimeModule]:
    rows: list[RuntimeModule] = []
    for module_id in module_ids:
        module = get_runtime_module(module_id)
        if module:
            rows.append(module)
    return rows


def module_signature(module_ids: list[str]) -> str:
    rows = list_runtime_modules(module_ids)
    if not rows:
        return "unknown"
    normalized = "|".join(sorted(f"{row.module_id}:{row.version}" for row in rows))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:20]


def default_module_signature() -> str:
    return module_signature(
        [
            "scene_world",
            "camera_stack",
            "controller_stack",
            "combat_stack",
            "progression_stack",
            "feedback_stack",
            "hud_stack",
        ]
    )
