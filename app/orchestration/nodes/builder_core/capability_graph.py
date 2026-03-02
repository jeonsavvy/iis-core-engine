from __future__ import annotations

from typing import Any


def build_capability_graph(profile: dict[str, Any]) -> dict[str, Any]:
    camera = str(profile.get("camera_model", "third_person"))
    locomotion = str(profile.get("locomotion_model", "on_foot"))
    interaction = str(profile.get("interaction_model", "action"))
    progression = str(profile.get("progression_model", "objective_chain"))
    world = str(profile.get("world_topology", "arena"))

    nodes = [
        {"id": "camera", "value": camera},
        {"id": "locomotion", "value": locomotion},
        {"id": "interaction", "value": interaction},
        {"id": "progression", "value": progression},
        {"id": "world", "value": world},
    ]
    edges = [
        {"from": "camera", "to": "interaction"},
        {"from": "locomotion", "to": "world"},
        {"from": "interaction", "to": "progression"},
        {"from": "world", "to": "progression"},
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_plan(profile: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    camera = str(profile.get("camera_model", "third_person"))
    locomotion = str(profile.get("locomotion_model", "on_foot"))
    interaction = str(profile.get("interaction_model", "action"))
    combat = str(profile.get("combat_model", "none"))
    progression = str(profile.get("progression_model", "objective_chain"))

    modules: list[str] = [
        "scene_world",
        "camera_stack",
        "controller_stack",
        "combat_stack",
        "progression_stack",
        "feedback_stack",
        "hud_stack",
    ]

    optional: list[str] = []
    if locomotion == "flight":
        optional.append("flight_physics")
    if locomotion == "vehicle":
        optional.append("vehicle_dynamics")
    if interaction == "ranged_combat":
        optional.append("projectile_system")
    if interaction == "melee_combat" or combat == "melee":
        optional.append("combo_chain")
    if progression == "checkpoint_lap":
        optional.append("checkpoint_loop")
    if camera in {"first_person", "chase"}:
        optional.append("camera_fx")

    return {
        "primary_modules": modules,
        "optional_modules": optional,
        "graph_nodes": graph.get("nodes", []),
        "graph_edges": graph.get("edges", []),
        "capability_tags": profile.get("capability_tags", []),
    }
