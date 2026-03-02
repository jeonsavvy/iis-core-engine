from __future__ import annotations

from app.orchestration.nodes.builder_parts.substrates.base import SubstrateProfile


RACER_3D_LOOPS = {"f1_formula_circuit_3d", "webgl_three_runner", "lane_dodge_racer"}


def resolve(core_loop_type: str) -> SubstrateProfile | None:
    if core_loop_type not in RACER_3D_LOOPS:
        return None
    return SubstrateProfile(
        substrate_id="racer_3d",
        camera_model="chase_or_cockpit",
        interaction_model="vehicle_control",
        render_bias="speed_depth",
        objective_hint="속도감·코너 라인·체크포인트 피드백을 유지합니다.",
    )
