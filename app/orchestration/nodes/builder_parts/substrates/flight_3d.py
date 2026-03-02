from __future__ import annotations

from app.orchestration.nodes.builder_parts.substrates.base import SubstrateProfile


FLIGHT_3D_LOOPS = {"flight_sim_3d"}


def resolve(core_loop_type: str) -> SubstrateProfile | None:
    if core_loop_type not in FLIGHT_3D_LOOPS:
        return None
    return SubstrateProfile(
        substrate_id="flight_3d",
        camera_model="cockpit_or_chase",
        interaction_model="flight_control",
        render_bias="altitude_readability",
        objective_hint="피치·롤·요와 항로 링 가독성을 유지합니다.",
    )
