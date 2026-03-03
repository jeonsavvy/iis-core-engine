"""Genre Engine Registry for quality-targeted game generation.

Maps game genres to required systems, reference patterns, and minimum
quality criteria. Used by the codegen pipeline to inject genre-specific
guidance into LLM prompts and enforce quality floors per genre.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenreEngine:
    """Quality engine spec for a single genre family."""

    name: str
    required_systems: list[str]
    reference_patterns: list[str]
    min_functions: int = 10
    min_lines: int = 320
    min_shaders: int = 1
    min_states: int = 2
    prompt_hints: str = ""


_REGISTRY: dict[str, GenreEngine] = {
    "space_combat": GenreEngine(
        name="space_combat",
        required_systems=[
            "procedural_planet_lod",
            "flight_physics_6dof",
            "npc_fsm_ai",
            "laser_combat",
            "particle_trails",
            "instanced_asteroids",
        ],
        reference_patterns=[
            "QuadTree LOD terrain with simplex noise fbm",
            "NPC FSM: orbit → deepspace → dying states",
            "InstancedMesh for 500+ asteroids",
            "Custom GLSL atmospheric scattering shader",
            "6DOF flight with pitch/yaw/roll/throttle",
            "Raycaster-based laser targeting",
        ],
        min_functions=14,
        min_lines=420,
        min_shaders=1,
        min_states=3,
        prompt_hints=(
            "Implement a space combat game with procedural planets using QuadTree LOD, "
            "6DOF flight physics, NPC fighters with FSM AI (orbit/chase/attack/dying), "
            "laser combat with raycaster targeting, InstancedMesh asteroids (500+), "
            "engine particle trails, atmospheric scattering GLSL shader, "
            "and at least 4 player states: FLIGHT, LANDED, ON_FOOT, DEAD."
        ),
    ),
    "racing_3d": GenreEngine(
        name="racing_3d",
        required_systems=[
            "procedural_road",
            "vehicle_physics",
            "drift_mechanics",
            "checkpoint_system",
            "ai_opponents",
            "speed_effects",
        ],
        reference_patterns=[
            "Procedural road with bezier curves and banking",
            "Vehicle physics: acceleration, braking, drift angle",
            "AI opponents following racing line with rubber-banding",
            "Speed blur post-processing shader",
            "Checkpoint/lap system with split times",
            "Dynamic camera shake on boost/collision",
        ],
        min_functions=12,
        min_lines=340,
        min_shaders=1,
        min_states=2,
        prompt_hints=(
            "Implement a 3D racing game with procedural road generation, "
            "realistic vehicle physics (acceleration, braking, drift), "
            "AI opponents with racing line following, checkpoint/lap system, "
            "speed blur GLSL shader, dynamic camera, and at least 3 states: "
            "RACING, PAUSED, FINISHED."
        ),
    ),
    "fps_arena": GenreEngine(
        name="fps_arena",
        required_systems=[
            "first_person_camera",
            "raycaster_weapons",
            "arena_map",
            "enemy_ai_fsm",
            "health_ammo",
            "hit_effects",
        ],
        reference_patterns=[
            "First-person camera with mouse look and WASD movement",
            "Raycaster-based hitscan weapons with recoil",
            "Procedural arena geometry with corridors and rooms",
            "Enemy AI FSM: patrol → alert → chase → attack",
            "Health/ammo pickup system with respawn",
            "Hit impact particles and screen shake",
        ],
        min_functions=12,
        min_lines=340,
        min_shaders=1,
        min_states=2,
        prompt_hints=(
            "Implement a first-person arena shooter with mouse look camera, "
            "raycaster-based weapons, procedural arena map, enemy AI FSM, "
            "health/ammo pickups, hit effects, and at least 3 states: "
            "PLAYING, DEAD, MENU."
        ),
    ),
    "platformer_3d": GenreEngine(
        name="platformer_3d",
        required_systems=[
            "player_controller",
            "jump_physics",
            "procedural_platforms",
            "collectibles",
            "camera_follow",
            "hazards",
        ],
        reference_patterns=[
            "Character controller with ground detection via raycaster",
            "Jump physics with coyote time and variable height",
            "Procedural platform placement with difficulty scaling",
            "Collectible items with magnet/attraction effect",
            "Smooth third-person camera with orbit controls",
            "Hazard patterns: moving, rotating, timed",
        ],
        min_functions=10,
        min_lines=300,
        min_shaders=1,
        min_states=2,
        prompt_hints=(
            "Implement a 3D platformer with character controller, jump physics "
            "(coyote time, variable height), procedural platforms, collectibles, "
            "hazards, smooth camera follow, and at least 3 states: "
            "PLAYING, DEAD, VICTORY."
        ),
    ),
    "arcade_generic": GenreEngine(
        name="arcade_generic",
        required_systems=[
            "game_loop",
            "player_movement",
            "enemy_spawn",
            "scoring",
            "particle_effects",
            "difficulty_scaling",
        ],
        reference_patterns=[
            "Core game loop with delta-time based movement",
            "Player with analog input (smooth acceleration/deceleration)",
            "Enemy spawn tables with wave escalation",
            "Combo-based scoring with visual multiplier feedback",
            "Particle burst effects on hit/collect/destroy",
            "Progressive difficulty scaling on timer/score thresholds",
        ],
        min_functions=8,
        min_lines=220,
        min_shaders=0,
        min_states=2,
        prompt_hints=(
            "Implement a polished arcade game with smooth player movement, "
            "enemy wave system with escalation, combo scoring, particle effects, "
            "progressive difficulty, custom GLSL background shader, "
            "and at least 2 states: PLAYING, GAME_OVER."
        ),
    ),
}


def resolve_genre_engine(genre: str, keyword: str = "") -> GenreEngine:
    """Resolve the best matching genre engine from GDD genre and keyword."""
    genre_lower = genre.strip().casefold()
    keyword_lower = keyword.strip().casefold()
    combined = f"{genre_lower} {keyword_lower}"

    if any(t in combined for t in ("space", "flight", "우주", "전투기", "비행")):
        return _REGISTRY["space_combat"]
    if any(t in combined for t in ("racing", "race", "f1", "formula", "레이싱", "drift", "드리프트")):
        return _REGISTRY["racing_3d"]
    if any(t in combined for t in ("fps", "shooter", "슈팅", "arena", "gun")):
        return _REGISTRY["fps_arena"]
    if any(t in combined for t in ("platform", "플랫폼", "jump", "점프", "mario")):
        return _REGISTRY["platformer_3d"]

    # Fallback: check registry keys directly
    for key, engine in _REGISTRY.items():
        if key in genre_lower:
            return engine

    return _REGISTRY["arcade_generic"]


def get_genre_reference_prompt(engine: GenreEngine) -> str:
    """Build a genre-specific reference prompt section for LLM codegen."""
    systems = "\n".join(f"  - {s}" for s in engine.required_systems)
    patterns = "\n".join(f"  - {p}" for p in engine.reference_patterns)
    return (
        f"=== GENRE ENGINE: {engine.name.upper()} ===\n"
        f"Required systems:\n{systems}\n\n"
        f"Reference implementation patterns:\n{patterns}\n\n"
        f"Minimum complexity: {engine.min_functions} functions, "
        f"{engine.min_lines} lines, {engine.min_shaders} GLSL shaders, "
        f"{engine.min_states} game states.\n\n"
        f"Genre guidance: {engine.prompt_hints}\n"
        f"=== END GENRE ENGINE ===\n"
    )


def get_genre_quality_floor(engine: GenreEngine) -> dict[str, int]:
    """Return genre-specific quality floor thresholds."""
    return {
        "min_functions": engine.min_functions,
        "min_lines": engine.min_lines,
        "min_shaders": engine.min_shaders,
        "min_states": engine.min_states,
    }
