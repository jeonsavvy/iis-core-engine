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
            "fantasy": "open-wheel circuit racing with lap time pressure",
            "camera_style": "chase_cam",
            "progression": ["lap timer", "checkpoints", "time attack"],
            "must_have_mechanics": ["steer", "throttle", "brake", "lap timing", "restart"],
            "must_not_degrade_into": ["endless obstacle runner", "single-lane dodge game"],
            "scaffold_key": scaffold_key,
            "quality_target": "web_high_fidelity_racing",
            "benchmark_reference": "openwheel_circuit_baseline_v1",
            "degradation_guard": ["endless obstacle runner", "single-lane dodge game"],
            "first_frame_requirements": [
                "visible vehicle in lower third",
                "visible circuit path in center field",
                "readable lap timer",
                "clear start-finish or checkpoint indicator",
            ],
        }

    if any(token in text for token in ("flight", "dogfight", "pilot", "space shooter", "우주", "도그파이트", "비행")):
        scaffold_key = "three_space_dogfight_seed"
        return {
            "engine_mode": "3d_three",
            "archetype": "flight_shooter_space_dogfight_3d",
            "fantasy": "three-dimensional space dogfight combat",
            "camera_style": "chase_hud_hybrid",
            "progression": ["enemy waves", "target pursuit", "survival pressure"],
            "must_have_mechanics": ["pitch", "roll", "yaw", "throttle", "primary fire", "boost"],
            "must_not_degrade_into": ["forward auto-scroll shooter", "flat lane shooter"],
            "scaffold_key": scaffold_key,
            "quality_target": "quality_idea_plus",
            "benchmark_reference": "/root/workspace/create/coding/iis/quality_idea.md",
            "degradation_guard": ["forward auto-scroll shooter", "flat lane shooter"],
            "first_frame_requirements": [
                "visible reticle",
                "target/combat context",
                "ship movement cues",
                "space depth layers",
            ],
        }

    if any(token in text for token in ("top-down", "topdown", "탑뷰", "twin-stick", "twinstick", "아레나 슈터")):
        scaffold_key = "phaser_twinstick_arena_seed"
        return {
            "engine_mode": "2d_phaser",
            "archetype": "topdown_shooter_twinstick_2d",
            "fantasy": "twin-stick arena shooter with readable combat feedback",
            "camera_style": "top_down_arena",
            "progression": ["waves", "mobility mastery", "weapon rhythm"],
            "must_have_mechanics": ["move", "aim", "fire", "dash", "restart"],
            "must_not_degrade_into": ["single-button clicker", "basic 8-way shooter without dash"],
            "scaffold_key": scaffold_key,
            "quality_target": "web_high_fidelity_twinstick",
            "benchmark_reference": "twinstick_arena_baseline_v1",
            "degradation_guard": ["single-button clicker", "basic 8-way shooter without dash"],
            "first_frame_requirements": [
                "player/enemy separation",
                "readable arena",
                "combat feedback cues",
                "wave pressure state",
            ],
        }

    return {
        "engine_mode": "unknown",
        "archetype": "generic",
        "fantasy": "prompt-driven browser game",
        "camera_style": "contextual",
        "progression": [],
        "must_have_mechanics": [],
        "must_not_degrade_into": [],
        "scaffold_key": None,
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
    }
