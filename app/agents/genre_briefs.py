from __future__ import annotations

from typing import Any


def build_genre_brief(*, user_prompt: str, genre_hint: str = "") -> dict[str, Any]:
    text = f"{user_prompt} {genre_hint}".casefold()

    if any(token in text for token in ("f1", "formula", "open-wheel", "open wheel", "서킷", "lap", "랩타임", "circuit")):
        return {
            "engine_mode": "3d_three",
            "archetype": "racing_openwheel_circuit_3d",
            "fantasy": "open-wheel circuit racing with lap time pressure",
            "camera_style": "chase_cam",
            "progression": ["lap timer", "checkpoints", "time attack"],
            "must_have_mechanics": ["steer", "throttle", "brake", "lap timing", "restart"],
            "must_not_degrade_into": ["endless obstacle runner", "single-lane dodge game"],
        }

    if any(token in text for token in ("flight", "dogfight", "pilot", "space shooter", "우주", "도그파이트", "비행")):
        return {
            "engine_mode": "3d_three",
            "archetype": "flight_shooter_space_dogfight_3d",
            "fantasy": "three-dimensional space dogfight combat",
            "camera_style": "chase_hud_hybrid",
            "progression": ["enemy waves", "target pursuit", "survival pressure"],
            "must_have_mechanics": ["pitch", "roll", "yaw", "throttle", "primary fire", "boost"],
            "must_not_degrade_into": ["forward auto-scroll shooter", "flat lane shooter"],
        }

    if any(token in text for token in ("top-down", "topdown", "탑뷰", "twin-stick", "twinstick", "아레나 슈터")):
        return {
            "engine_mode": "2d_phaser",
            "archetype": "topdown_shooter_twinstick_2d",
            "fantasy": "twin-stick arena shooter with readable combat feedback",
            "camera_style": "top_down_arena",
            "progression": ["waves", "mobility mastery", "weapon rhythm"],
            "must_have_mechanics": ["move", "aim", "fire", "dash", "restart"],
            "must_not_degrade_into": ["single-button clicker", "basic 8-way shooter without dash"],
        }

    return {
        "engine_mode": "unknown",
        "archetype": "generic",
        "fantasy": "prompt-driven browser game",
        "camera_style": "contextual",
        "progression": [],
        "must_have_mechanics": [],
        "must_not_degrade_into": [],
    }


def scaffold_seed_for_brief(brief: dict[str, Any]) -> dict[str, Any] | None:
    archetype = str(brief.get("archetype", ""))
    if archetype == "racing_openwheel_circuit_3d":
        return {
            "seed_name": "three_openwheel_circuit_seed",
            "engine_mode": "3d_three",
            "seed_outline": [
                "loop track / circuit road mesh",
                "open-wheel race car silhouette and chase camera",
                "lap timer + checkpoint progression",
                "steer/throttle/brake separation",
                "requestAnimationFrame loop + restart flow",
            ],
        }
    if archetype == "flight_shooter_space_dogfight_3d":
        return {
            "seed_name": "three_space_dogfight_seed",
            "engine_mode": "3d_three",
            "seed_outline": [
                "starfield / space arena depth",
                "ship orientation controls (pitch/roll/yaw)",
                "throttle + boost + primary fire",
                "targeting HUD / reticle shell",
                "enemy wave and pursuit loop",
            ],
        }
    if archetype == "topdown_shooter_twinstick_2d":
        return {
            "seed_name": "phaser_twinstick_arena_seed",
            "engine_mode": "2d_phaser",
            "seed_outline": [
                "arena bounds and wave spawn loop",
                "move/aim/fire separation",
                "dash / mobility skill",
                "readable HUD and hit feedback",
                "restart flow and progression loop",
            ],
        }
    return None
