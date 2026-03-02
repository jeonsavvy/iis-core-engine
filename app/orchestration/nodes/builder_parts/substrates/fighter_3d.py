from __future__ import annotations

from app.orchestration.nodes.builder_parts.substrates.base import SubstrateProfile


FIGHTER_3D_LOOPS = {"comic_action_brawler_3d", "duel_brawler"}


def resolve(core_loop_type: str) -> SubstrateProfile | None:
    if core_loop_type not in FIGHTER_3D_LOOPS:
        return None
    return SubstrateProfile(
        substrate_id="fighter_3d",
        camera_model="third_person_close",
        interaction_model="melee_combo",
        render_bias="impact_readability",
        objective_hint="근접 교전의 타격감과 카운터 타이밍을 유지합니다.",
    )
