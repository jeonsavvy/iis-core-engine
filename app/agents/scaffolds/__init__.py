from __future__ import annotations

from app.agents.scaffolds.base import ScaffoldSeed
from app.agents.scaffolds.three_lowpoly_island_flight_seed import SEED as THREE_LOWPOLY_ISLAND_FLIGHT_SEED
from app.agents.scaffolds.phaser_twinstick_arena_seed import SEED as PHASER_TWINSTICK_ARENA_SEED
from app.agents.scaffolds.three_openwheel_circuit_seed import SEED as THREE_OPENWHEEL_CIRCUIT_SEED
from app.agents.scaffolds.three_space_dogfight_seed import SEED as THREE_SPACE_DOGFIGHT_SEED

_SEEDS: dict[str, ScaffoldSeed] = {
    THREE_OPENWHEEL_CIRCUIT_SEED.key: THREE_OPENWHEEL_CIRCUIT_SEED,
    THREE_LOWPOLY_ISLAND_FLIGHT_SEED.key: THREE_LOWPOLY_ISLAND_FLIGHT_SEED,
    THREE_SPACE_DOGFIGHT_SEED.key: THREE_SPACE_DOGFIGHT_SEED,
    PHASER_TWINSTICK_ARENA_SEED.key: PHASER_TWINSTICK_ARENA_SEED,
}


def get_scaffold_seed(key: str) -> ScaffoldSeed | None:
    return _SEEDS.get(key)


def list_scaffold_keys() -> list[str]:
    return sorted(_SEEDS.keys())


__all__ = ["ScaffoldSeed", "get_scaffold_seed", "list_scaffold_keys"]
