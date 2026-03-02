from __future__ import annotations

from app.orchestration.nodes.builder_parts.substrates.base import SubstrateProfile


TOPDOWN_2D_LOOPS = {"topdown_roguelike_shooter"}


def resolve(core_loop_type: str) -> SubstrateProfile | None:
    if core_loop_type not in TOPDOWN_2D_LOOPS:
        return None
    return SubstrateProfile(
        substrate_id="topdown_2d",
        camera_model="top_down",
        interaction_model="dodger_shooter",
        render_bias="silhouette_density",
        objective_hint="탑다운 이동/회피와 탄막 가독성을 유지합니다.",
    )
