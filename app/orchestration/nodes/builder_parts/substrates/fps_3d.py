from __future__ import annotations

from app.orchestration.nodes.builder_parts.substrates.base import SubstrateProfile


FPS_3D_LOOPS = {"arena_shooter"}


def resolve(core_loop_type: str) -> SubstrateProfile | None:
    if core_loop_type not in FPS_3D_LOOPS:
        return None
    return SubstrateProfile(
        substrate_id="fps_3d",
        camera_model="first_person",
        interaction_model="ranged_combat",
        render_bias="aim_feedback",
        objective_hint="시야 이동, 조준 피드백, 탄착 명료도를 우선 보장합니다.",
    )
