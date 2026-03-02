from __future__ import annotations

import hashlib
import re
from typing import Any


def _normalize_tokens(*values: str) -> list[str]:
    merged = " ".join(value for value in values if value).casefold()
    return [token for token in re.split(r"[^a-z0-9가-힣]+", merged) if token]


def _contains(tokens: set[str], *keywords: str) -> bool:
    return any(keyword in tokens for keyword in keywords)


def extract_capability_profile(
    *,
    keyword: str,
    title: str,
    genre: str,
    core_loop_type: str,
    analyze_contract: dict[str, Any] | None = None,
    plan_contract: dict[str, Any] | None = None,
    design_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tokens = _normalize_tokens(keyword, title, genre, core_loop_type)
    token_set = set(tokens)

    camera_model = "third_person"
    if _contains(token_set, "fps", "first", "1인칭", "cockpit"):
        camera_model = "first_person"
    elif _contains(token_set, "topdown", "탑다운", "탑뷰"):
        camera_model = "top_down"
    elif _contains(token_set, "flight", "비행"):
        camera_model = "chase"

    locomotion_model = "on_foot"
    if _contains(token_set, "racing", "race", "레이싱", "drift", "f1", "formula"):
        locomotion_model = "vehicle"
    elif _contains(token_set, "flight", "비행", "pilot", "aircraft"):
        locomotion_model = "flight"

    interaction_model = "action"
    combat_model = "none"
    if _contains(token_set, "fighter", "격투", "brawler", "boxing", "fight", "duel"):
        interaction_model = "melee_combat"
        combat_model = "melee"
    elif _contains(token_set, "fps", "shooter", "shoot", "사격", "슈팅", "총"):
        interaction_model = "ranged_combat"
        combat_model = "ranged"
    elif _contains(token_set, "racing", "race", "레이싱", "flight", "비행"):
        interaction_model = "navigation"

    world_topology = "arena"
    if locomotion_model == "vehicle":
        world_topology = "track"
    elif locomotion_model == "flight":
        world_topology = "airspace"
    elif camera_model == "top_down":
        world_topology = "zone_map"

    progression_model = "objective_chain"
    if _contains(token_set, "roguelike", "로그라이크", "survival", "생존"):
        progression_model = "run_escalation"
    elif locomotion_model == "vehicle":
        progression_model = "checkpoint_lap"

    fail_state_model = "hp_or_timer"
    if locomotion_model == "vehicle":
        fail_state_model = "collision_or_timer"

    request_hash = hashlib.sha256(f"{keyword}|{title}|{genre}|{core_loop_type}".encode("utf-8")).hexdigest()[:12]
    complexity_tier = "standard"
    if len(token_set) >= 12 or _contains(token_set, "openworld", "sandbox", "멀티", "procedural"):
        complexity_tier = "high"

    capability_tags = sorted(
        {
            f"camera:{camera_model}",
            f"locomotion:{locomotion_model}",
            f"interaction:{interaction_model}",
            f"combat:{combat_model}",
            f"world:{world_topology}",
            f"progression:{progression_model}",
            f"fail_state:{fail_state_model}",
        }
    )
    if _contains(token_set, "3d", "webgl", "voxel", "first", "third", "입체", "fps", "tps"):
        capability_tags.append("render:3d")
    else:
        capability_tags.append("render:2d")

    profile: dict[str, Any] = {
        "profile_id": f"cp-{request_hash}",
        "request_tokens": tokens[:48],
        "core_loop_type": core_loop_type,
        "camera_model": camera_model,
        "locomotion_model": locomotion_model,
        "interaction_model": interaction_model,
        "combat_model": combat_model,
        "world_topology": world_topology,
        "progression_model": progression_model,
        "fail_state_model": fail_state_model,
        "complexity_tier": complexity_tier,
        "capability_tags": capability_tags,
        "contract_inputs": {
            "analyze_scope_in": (analyze_contract or {}).get("scope_in", []),
            "plan_core_mechanics": (plan_contract or {}).get("core_mechanics", []),
            "design_scene_layers": (design_contract or {}).get("scene_layers", []),
        },
    }
    return profile
