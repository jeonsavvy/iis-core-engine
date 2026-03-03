from __future__ import annotations

import hashlib
import re
from typing import Any


def _normalize_tokens(*values: str) -> list[str]:
    merged = " ".join(value for value in values if value).casefold()
    return [token for token in re.split(r"[^a-z0-9가-힣]+", merged) if token]


def _contains(tokens: set[str], merged_compact: str, *keywords: str) -> bool:
    for keyword in keywords:
        normalized_keyword = keyword.casefold().replace(" ", "")
        if not normalized_keyword:
            continue
        if normalized_keyword in tokens:
            return True
        if normalized_keyword in merged_compact:
            return True
    return False


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
    merged_text = " ".join(value for value in (keyword, title, genre, core_loop_type) if value).casefold()
    merged_compact = re.sub(r"[^a-z0-9가-힣]+", "", merged_text)
    tokens = _normalize_tokens(keyword, title, genre, core_loop_type)
    token_set = set(tokens)
    vehicle_keywords = {
        "car",
        "cars",
        "auto",
        "automobile",
        "vehicle",
        "vehicles",
        "truck",
        "trucks",
        "driving",
        "drive",
        "driver",
        "racing",
        "race",
        "drift",
        "formula",
        "f1",
        "레이싱",
        "자동차",
        "차량",
        "트럭",
        "운전",
        "드라이브",
        "주행",
        "카레이싱",
        "조향",
    }
    flight_keywords = {"flight", "비행", "pilot", "aircraft", "flightsim", "조종", "항공", "파일럿"}
    melee_keywords = {"fighter", "격투", "brawler", "boxing", "fight", "duel", "combat", "근접"}
    ranged_keywords = {"fps", "shooter", "shoot", "사격", "슈팅", "총", "gun", "rifle"}

    camera_model = "third_person"
    if _contains(token_set, merged_compact, "fps", "first", "1인칭", "cockpit"):
        camera_model = "first_person"
    elif _contains(token_set, merged_compact, "topdown", "탑다운", "탑뷰"):
        camera_model = "top_down"
    elif _contains(token_set, merged_compact, *flight_keywords):
        camera_model = "chase"

    locomotion_model = "on_foot"
    if _contains(token_set, merged_compact, *vehicle_keywords):
        locomotion_model = "vehicle"
    elif _contains(token_set, merged_compact, *flight_keywords):
        locomotion_model = "flight"
    if locomotion_model == "vehicle" and camera_model == "third_person":
        camera_model = "chase"

    interaction_model = "action"
    combat_model = "none"
    if _contains(token_set, merged_compact, *melee_keywords):
        interaction_model = "melee_combat"
        combat_model = "melee"
    elif _contains(token_set, merged_compact, *ranged_keywords):
        interaction_model = "ranged_combat"
        combat_model = "ranged"
    elif locomotion_model in {"vehicle", "flight"}:
        interaction_model = "navigation"

    world_topology = "arena"
    if locomotion_model == "vehicle":
        world_topology = "track"
    elif locomotion_model == "flight":
        world_topology = "airspace"
    elif camera_model == "top_down":
        world_topology = "zone_map"

    progression_model = "objective_chain"
    if _contains(token_set, merged_compact, "roguelike", "로그라이크", "survival", "생존"):
        progression_model = "run_escalation"
    elif locomotion_model == "vehicle":
        progression_model = "checkpoint_lap"

    fail_state_model = "hp_or_timer"
    if locomotion_model == "vehicle":
        fail_state_model = "collision_or_timer"

    request_hash = hashlib.sha256(f"{keyword}|{title}|{genre}|{core_loop_type}".encode("utf-8")).hexdigest()[:12]
    complexity_tier = "standard"
    if len(token_set) >= 12 or _contains(token_set, merged_compact, "openworld", "sandbox", "멀티", "procedural"):
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
    explicit_2d_request = _contains(
        token_set,
        merged_compact,
        "2d",
        "pixel",
        "도트",
        "플랫",
        "2차원",
        "플랫포머",
        "플랫포머게임",
        "턴제",
        "카주얼2d",
        "카드게임",
        "텍스트",
        "보드게임",
    )
    if explicit_2d_request:
        capability_tags.append("render:2d")
    else:
        capability_tags.append("render:3d")

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
