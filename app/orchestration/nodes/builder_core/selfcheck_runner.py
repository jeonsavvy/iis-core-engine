from __future__ import annotations

import re
from typing import Any


def _count_present_tokens(source: str, tokens: tuple[str, ...]) -> int:
    return sum(1 for token in tokens if token in source)


def _resolve_render_mode(capability_profile: dict[str, Any]) -> str:
    tags = capability_profile.get("capability_tags")
    if isinstance(tags, list):
        normalized = {str(item).strip().casefold() for item in tags if str(item).strip()}
        if "render:2d" in normalized:
            return "2d"
    return "3d"


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
    render_mode = _resolve_render_mode(capability_profile)

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

    if render_mode == "2d":
        input_tokens = (
            "keycodes.w",
            "keycodes.a",
            "keycodes.s",
            "keycodes.d",
            "cursor.right",
            "cursor.left",
            "cursor.up",
            "cursor.down",
            "space",
            "shift",
            "keys.r",
        )
    else:
        input_tokens = (
            "keydown",
            "keyup",
            "arrowup",
            "arrowdown",
            "arrowleft",
            "arrowright",
            'key === "r"',
            "shift",
            "space",
        )
    state_tokens = ("running", "elapsed", "timeleft", "endgame", "resetgame", "objective")
    if render_mode == "2d":
        object_tokens = ("this.player", "this.enemies", "this.checkpoints", "this.pickups", "phaser")
        feedback_tokens = ("overlay", "overlay-text", "score", "timer", "hp", "settintfill", "cameras.main.shake")
    else:
        object_tokens = ("makeplayermesh", "makeenemymesh", "makecheckpointmesh", "makepickupmesh", "scene.add", "worldroot")
        feedback_tokens = ("overlay", "overlay-text", "score", "timer", "hp", "renderer.render")

    input_coverage = _count_present_tokens(lowered, input_tokens)
    state_coverage = _count_present_tokens(lowered, state_tokens)
    object_coverage = _count_present_tokens(lowered, object_tokens)
    feedback_coverage = _count_present_tokens(lowered, feedback_tokens)

    mesh_variety = 0
    if render_mode == "3d":
        mesh_tokens = (
            "boxgeometry",
            "spheregeometry",
            "cylindergeometry",
            "torusgeometry",
            "octahedrongeometry",
            "capsulegeometry",
            "conegeometry",
        )
        mesh_variety = len({token for token in mesh_tokens if token in lowered})

    controls_text_match = re.search(r"<p id=\"control-guide\">([^<]+)</p>", html_content, flags=re.IGNORECASE)
    controls_text = controls_text_match.group(1).strip() if controls_text_match else ""
    controls_lower = controls_text.casefold()
    objective_text_match = re.search(r"<span id=\"objective\">([^<]+)</span>", html_content, flags=re.IGNORECASE)
    objective_text = objective_text_match.group(1).strip() if objective_text_match else ""
    objective_lower = objective_text.casefold()
    subtitle_match = re.search(r"<div class=\"subtitle\">([^<]+)</div>", html_content, flags=re.IGNORECASE)
    subtitle_text = subtitle_match.group(1).strip() if subtitle_match else ""
    subtitle_slug_like = bool(re.search(r"\b[a-z0-9]+(?:-[a-z0-9]+){2,}\b", subtitle_text.casefold()))

    jargon_pattern = re.compile(r"\b(?:relic|synergy|syn\s*\d|build\(|lv\.?\s*\d+|xp\s*[:/\d]|w\d+)\b")
    objective_placeholder_pattern = re.compile(
        r"(directional movement|core movement|primary action loop|objective_chain|timing\b)",
        flags=re.IGNORECASE,
    )

    checks: dict[str, bool] = {
        "rqc_version_declared": bool(rqc_version.strip()),
        "single_html_document": "<!doctype html>" in lowered and lowered.count("<html") == 1,
        "render_loop": (
            "requestanimationframe(animate)" in lowered and "renderer.render(scene, camera)" in lowered
            if render_mode == "3d"
            else "new phaser.game" in lowered and "update(_time, delta)" in lowered
        ),
        "input_axis_coverage": input_coverage >= 6,
        "state_machine_coverage": state_coverage >= 4,
        "object_variety": object_coverage >= 5,
        "mesh_variety": mesh_variety >= 4 if render_mode == "3d" else True,
        "feedback_fidelity": feedback_coverage >= 4,
        "progression_loop": (
            "spawncheckpoint" in lowered and "timeleft" in lowered and "score" in lowered
            if render_mode == "3d"
            else "spawnwave" in lowered and "timeleft" in lowered and "score" in lowered and "checkpoint" in lowered
        ),
        "boot_flag_and_leaderboard": "window.__iis_game_boot_ok = true" in lowered and "window.iisleaderboard" in lowered,
        "no_start_gate": "tap to start" not in lowered and "click to start" not in lowered and "press start" not in lowered,
        "no_hud_jargon": not bool(jargon_pattern.search(lowered)),
        "objective_text_quality": bool(objective_text) and not bool(objective_placeholder_pattern.search(objective_lower)),
        "subtitle_no_slug_noise": not subtitle_slug_like,
        "overflow_guard": "overflow: hidden" in lowered and "overflow-guard" in lowered,
        "controls_single_source": controls_text != "" and 2 <= lowered.count("control-guide") <= 4,
        "required_modules_present": all(module_id in all_modules for module_id in required_primary),
    }
    if render_mode == "3d":
        checks["threejs_runtime"] = "import * as three from \"three\"" in lowered
        checks["webgl_renderer"] = "new three.webglrenderer" in lowered
    else:
        checks["phaser_runtime"] = "new phaser.game" in lowered and "phaser.min.js" in lowered
        checks["phaser_scene_lifecycle"] = "class mainscene extends phaser.scene" in lowered and "create()" in lowered

    if locomotion == "flight":
        checks["flight_control_scheme_consistent"] = (
            "피치" in controls_text and "롤" in controls_text and "스로틀" in controls_text and "사격" not in controls_lower
        )
        checks["flight_runtime_present"] = "config.locomotionmodel === \"flight\"" in lowered and "makecheckpointmesh" in lowered
    elif locomotion == "vehicle":
        checks["vehicle_control_scheme_consistent"] = (
            "조향" in controls_text and "가속" in controls_text and "피치" not in controls_text
        )
        checks["vehicle_runtime_present"] = "config.locomotionmodel === \"vehicle\"" in lowered and "state.speed" in lowered
    else:
        checks["onfoot_control_scheme_consistent"] = (
            "이동" in controls_text and "재시작" in controls_text and "피치" not in controls_text
        )

    if interaction in {"melee_combat", "ranged_combat"}:
        checks["combat_interaction_present"] = (
            "resolvecombat" in lowered and "attackcooldown" in lowered
            if render_mode == "3d"
            else "tryattack" in lowered and "attackcooldown" in lowered
        )

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
        "mesh_variety": mesh_variety,
        "profile_id": capability_profile.get("profile_id"),
        "objective_text": objective_text,
        "subtitle_text": subtitle_text,
    }
