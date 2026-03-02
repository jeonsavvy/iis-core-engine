from __future__ import annotations

from app.orchestration.nodes.builder_parts.substrates.base import Resolver, SubstrateProfile
from app.orchestration.nodes.builder_parts.substrates import fighter_3d, flight_3d, fps_3d, racer_3d, topdown_2d

RESOLVERS: tuple[Resolver, ...] = (
    fighter_3d.resolve,
    fps_3d.resolve,
    racer_3d.resolve,
    flight_3d.resolve,
    topdown_2d.resolve,
)


def resolve_substrate_profile(core_loop_type: str) -> SubstrateProfile:
    normalized = str(core_loop_type or "").strip()
    for resolver in RESOLVERS:
        resolved = resolver(normalized)
        if resolved is not None:
            return resolved
    return SubstrateProfile(
        substrate_id="hybrid_dynamic",
        camera_model="request_driven",
        interaction_model="request_driven_action",
        render_bias="balanced",
        objective_hint="요청 의도를 유지한 하이브리드 상호작용을 구성합니다.",
    )
