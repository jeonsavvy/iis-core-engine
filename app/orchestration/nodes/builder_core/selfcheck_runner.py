from __future__ import annotations

import re
from typing import Any


def run_builder_selfcheck(
    *,
    html_content: str,
    capability_profile: dict[str, Any],
    module_plan: dict[str, Any],
    rqc_version: str,
) -> dict[str, Any]:
    lowered = html_content.casefold()
    locomotion = str(capability_profile.get("locomotion_model", "on_foot"))
    interaction = str(capability_profile.get("interaction_model", "action"))
    original_html = html_content
    required_primary = [
        "scene_world",
        "camera_stack",
        "controller_stack",
        "combat_stack",
        "progression_stack",
        "feedback_stack",
        "hud_stack",
    ]
    selected_modules = [str(item) for item in module_plan.get("primary_modules", []) if str(item).strip()]
    optional_modules = [str(item) for item in module_plan.get("optional_modules", []) if str(item).strip()]
    all_modules = selected_modules + optional_modules

    input_tokens = ("keydown", "arrowup", "arrowdown", "arrowleft", "arrowright", "space", "shift", "key === \"e\"", "key === \"q\"")
    input_coverage = sum(1 for token in input_tokens if token in lowered)
    state_tokens = ("explore", "combat", "dash", "recover")
    state_coverage = sum(1 for token in state_tokens if token in lowered)
    object_tokens = ("worldobjects", "enemies", "interactives", "projectiles", "player")
    object_coverage = sum(1 for token in object_tokens if token in lowered)
    feedback_tokens = ("feedback", "damagepulse", "hitpulse", "cameraShake".casefold(), "overlay")
    feedback_coverage = sum(1 for token in feedback_tokens if token in lowered)

    jargon_pattern = re.compile(r"\b(?:relic|synergy|syn\s*\d|build\(|lv\.?\s*\d+|xp\s*[:/\d])")
    checks: dict[str, bool] = {
        "rqc_version_declared": bool(rqc_version.strip()),
        "webgl_scene": "getcontext(\"webgl\"" in lowered,
        "perspective_camera": "createperspective" in lowered and "project(state" in lowered,
        "input_axis_coverage": input_coverage >= 6,
        "state_machine_coverage": state_coverage >= 4,
        "object_variety": object_coverage >= 4,
        "feedback_variety": feedback_coverage >= 3,
        "progression_loop": "objective" in lowered and "wave" in lowered and "score" in lowered,
        "dynamic_spawn_loop": "state.enemies.push" in lowered or "state.checkpoints.push" in lowered,
        "runtime_render_loop": "renderframe()" in lowered and "requestanimationframe(step)" in lowered,
        "no_start_gate": "tap to start" not in lowered and "click to start" not in lowered and "press start" not in lowered,
        "no_hud_jargon": not bool(jargon_pattern.search(lowered)),
        "overflow_guard": "overflow: hidden" in lowered and "overflow-guard" in lowered,
        "required_modules_present": all(module_id in all_modules for module_id in required_primary),
    }
    if locomotion == "flight":
        checks["flight_control_scheme_consistent"] = (
            "자세 제어: W/S 피치 · A/D 롤 · Q/E 요" in original_html
            and "이동: W/A/S/D 또는 방향키" not in original_html
        )
        checks["flight_objective_consistent"] = (
            ("waypoint" in lowered or "vector" in lowered or "airspace" in lowered)
            and "engage hostiles" not in lowered
        )
        checks["flight_checkpoint_loop"] = "state.checkpoints.push" in lowered and "checkpoint" in lowered
    if locomotion == "vehicle":
        checks["vehicle_control_scheme_consistent"] = (
            "조향:" in original_html and "피치" not in original_html
        )
        checks["vehicle_objective_consistent"] = (
            ("checkpoint" in lowered or "lap" in lowered or "racing line" in lowered)
            and "engage hostiles" not in lowered
        )
    if interaction in {"melee_combat", "ranged_combat"}:
        checks["combat_interaction_present"] = "state.projectiles.push" in lowered or "performattack" in lowered

    failed_reasons = [name for name, passed in checks.items() if not passed]
    score = int(round((sum(1 for passed in checks.values() if passed) / max(1, len(checks))) * 100))
    return {
        "passed": len(failed_reasons) == 0,
        "score": score,
        "checks": checks,
        "failed_reasons": failed_reasons,
        "input_axis_coverage": input_coverage,
        "state_coverage": state_coverage,
        "object_coverage": object_coverage,
        "feedback_coverage": feedback_coverage,
        "profile_id": capability_profile.get("profile_id"),
    }
