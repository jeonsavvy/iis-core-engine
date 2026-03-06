from __future__ import annotations

from typing import Any

from app.agents.scaffolds import get_scaffold_seed


def build_genre_brief(*, user_prompt: str, genre_hint: str = "") -> dict[str, Any]:
    text = f"{user_prompt} {genre_hint}".casefold()

    if any(token in text for token in ("f1", "formula", "open-wheel", "open wheel", "서킷", "lap", "랩타임", "circuit")):
        scaffold_key = "three_openwheel_circuit_seed"
        return {
            "engine_mode": "3d_three",
            "archetype": "racing_openwheel_circuit_3d",
            "fantasy": "open-wheel synthwave circuit racing with lap time pressure",
            "camera_style": "chase_cam",
            "progression": ["lap timer", "checkpoints", "time attack"],
            "must_have_mechanics": ["steer", "throttle", "brake", "lap timing", "restart"],
            "structural_contracts": [
                "checkpoint structures must behave as non-blocking trigger gates",
                "track confinement must keep the car on the circuit",
                "if the car falls below the safety threshold or leaves the circuit, respawn to the last checkpoint",
                "wrong-way state should only trigger when the car is moving against track direction on the circuit",
            ],
            "visual_contracts": [
                "synthwave or outrun style color language",
                "neon grid or glowing lane guidance on the track",
                "camera FOV should widen with speed",
                "start countdown and best-lap celebration UI must feel arcade and energetic",
            ],
            "must_not_degrade_into": ["endless obstacle runner", "single-lane dodge game"],
            "scaffold_key": scaffold_key,
            "asset_pack_key": "racing_synthwave_pack_v1",
            "quality_target": "web_high_fidelity_racing",
            "benchmark_reference": "openwheel_circuit_baseline_v1",
            "degradation_guard": ["endless obstacle runner", "single-lane dodge game"],
            "first_frame_requirements": [
                "visible vehicle in lower third",
                "visible circuit path in center field",
                "readable lap timer",
                "clear start-finish or checkpoint indicator",
                "synthwave grid and speed fantasy visible immediately",
            ],
        }

    if any(token in text for token in ("dogfight", "pilot", "space shooter", "우주", "도그파이트", "space combat", "플라이트 슈팅")):
        scaffold_key = "three_space_dogfight_seed"
        return {
            "engine_mode": "3d_three",
            "archetype": "flight_shooter_space_dogfight_3d",
            "fantasy": "three-dimensional space dogfight combat",
            "camera_style": "chase_hud_hybrid",
            "progression": ["enemy waves", "target pursuit", "survival pressure"],
            "must_have_mechanics": ["pitch", "roll", "yaw", "throttle", "primary fire", "boost"],
            "structural_contracts": [
                "dogfight baseline must preserve full attitude control",
                "enemy pursuit and enemy fire loops must remain active",
                "target lock and HUD readability must remain intact",
                "space depth must read clearly in the first frame",
            ],
            "must_not_degrade_into": ["forward auto-scroll shooter", "flat lane shooter"],
            "scaffold_key": scaffold_key,
            "quality_target": "quality_idea_plus",
            "benchmark_reference": "/root/workspace/create/coding/iis/quality_idea.md",
            "degradation_guard": ["forward auto-scroll shooter", "flat lane shooter"],
            "asset_pack_key": "space_dogfight_pack_v1",
            "visual_contracts": [
                "combat HUD must be readable in the first frame",
                "targeting and boost feedback must be immediately legible",
                "space depth and layered background must avoid flat darkness",
            ],
            "first_frame_requirements": [
                "visible reticle",
                "target/combat context",
                "ship movement cues",
                "space depth layers",
            ],
        }

    if any(token in text for token in ("프로펠러", "섬", "island", "coast", "비행기", "비행", "플라이트", "flight game", "하늘", "low-poly", "low poly", "링", "ring")):
        scaffold_key = "three_lowpoly_island_flight_seed"
        return {
            "engine_mode": "3d_three",
            "archetype": "flight_lowpoly_island_3d",
            "fantasy": "warm low-poly island flight with propeller plane and ring runs",
            "camera_style": "third_person_chase",
            "progression": ["ring routes", "coastal exploration", "smooth flight handling"],
            "must_have_mechanics": ["pitch", "bank", "throttle", "ring collect", "reset"],
            "structural_contracts": [
                "plane must be assembled from nose, wings, tail, and spinning propeller",
                "directional light, fog, sea, and island landmarks must remain active",
                "ring collect loop with particle or audio feedback must remain intact",
                "flight baseline must prioritize stable traversal over combat",
            ],
            "visual_contracts": [
                "flat shading low-poly style is mandatory",
                "warm sunrise or sunset directional light must define the mood",
                "sea, island silhouettes, and fog depth must read clearly in the first frame",
                "rings or coins must glow as readable traversal targets",
            ],
            "must_not_degrade_into": ["dark empty void flight", "space dogfight", "corridor flyer"],
            "scaffold_key": scaffold_key,
            "asset_pack_key": "island_flight_pack_v1",
            "quality_target": "web_stylized_lowpoly_flight",
            "benchmark_reference": "lowpoly_island_flight_baseline_v1",
            "degradation_guard": ["dark empty void flight", "space dogfight", "corridor flyer"],
            "first_frame_requirements": [
                "visible propeller plane silhouette",
                "visible island or sea landmark",
                "warm light and fog depth visible immediately",
                "readable ring traversal target in front of the player",
            ],
        }

    if any(token in text for token in ("top-down", "topdown", "탑뷰", "twin-stick", "twinstick", "아레나 슈터")):
        scaffold_key = "phaser_twinstick_arena_seed"
        return {
            "engine_mode": "2d_phaser",
            "archetype": "topdown_shooter_twinstick_2d",
            "fantasy": "neon bullet-hell twin-stick arena shooter with readable combat feedback",
            "camera_style": "top_down_arena",
            "progression": ["waves", "mobility mastery", "weapon rhythm"],
            "must_have_mechanics": ["move", "aim", "fire", "dash", "restart"],
            "structural_contracts": [
                "twin-stick move and aim must stay separated",
                "enemy pressure must include active hostile fire or pursuit",
                "dash feedback and arena readability must remain intact",
                "cover landmarks and combat spacing must remain readable",
            ],
            "visual_contracts": [
                "black background with cyan and magenta neon emphasis",
                "bloom-like glow, particles, and screen shake must support hits and deaths",
                "game state flow must include title/menu, wave escalation, and game-over restart",
            ],
            "must_not_degrade_into": ["single-button clicker", "basic 8-way shooter without dash"],
            "scaffold_key": scaffold_key,
            "asset_pack_key": "topdown_neon_pack_v1",
            "quality_target": "web_high_fidelity_twinstick",
            "benchmark_reference": "twinstick_arena_baseline_v1",
            "degradation_guard": ["single-button clicker", "basic 8-way shooter without dash"],
            "first_frame_requirements": [
                "player/enemy separation",
                "readable arena",
                "combat feedback cues",
                "wave pressure state",
                "neon bullet-hell look visible immediately",
            ],
        }

    return {
        "engine_mode": "unknown",
        "archetype": "generic",
        "fantasy": "prompt-driven browser game",
        "camera_style": "contextual",
        "progression": [],
        "must_have_mechanics": [],
        "structural_contracts": [],
        "visual_contracts": [],
        "must_not_degrade_into": [],
        "scaffold_key": None,
        "asset_pack_key": None,
        "quality_target": "generic_playable",
        "benchmark_reference": None,
        "degradation_guard": [],
        "first_frame_requirements": [],
    }


def scaffold_seed_for_brief(brief: dict[str, Any]) -> dict[str, Any] | None:
    scaffold_key = brief.get("scaffold_key")
    if not isinstance(scaffold_key, str) or not scaffold_key.strip():
        return None
    seed = get_scaffold_seed(scaffold_key)
    if seed is None:
        return None
    return {
        "seed_name": seed.key,
        "engine_mode": seed.engine_mode,
        "version": seed.version,
        "summary": seed.summary,
        "acceptance_tags": seed.acceptance_tags,
        "seed_outline": seed.summary,
        "asset_pack_key": brief.get("asset_pack_key"),
    }
