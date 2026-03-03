from __future__ import annotations
from typing import Any

from app.orchestration.nodes.builder_parts.genre_engine import get_genre_quality_floor, resolve_genre_engine
from app.core.config import Settings
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult


def evaluate_quality_contract(
    settings: Settings,
    html_content: str,
    *,
    design_spec: dict[str, Any] | None = None,
    genre: str | None = None,
    genre_engine: str | None = None,
    keyword: str | None = None,
) -> QualityGateResult:
    spec = design_spec or {}

    checks: list[tuple[str, bool, int]] = [
        ("boot_flag", "window.__iis_game_boot_ok" in html_content, 20),
        ("viewport_meta", "<meta name=\"viewport\"" in html_content, 20),
        ("leaderboard_contract", "window.IISLeaderboard" in html_content, 20),
        ("overflow_guard", "overflow-guard" in html_content, 15),
        ("overflow_policy", "data-overflow-policy" in html_content, 10),
        ("safe_area", "--safe-area-padding" in html_content, 15),
        ("canvas_present", "<canvas" in html_content.lower(), 20),
        ("game_loop_raf", "requestanimationframe" in html_content.lower(), 20),
        ("keyboard_input", "keydown" in html_content.lower(), 15),
        ("game_state_logic", "game over" in html_content.lower() or "overlay" in html_content.lower(), 10),
    ]

    viewport_width = spec.get("viewport_width")
    viewport_height = spec.get("viewport_height")
    min_font_size_px = spec.get("min_font_size_px")

    if isinstance(viewport_width, int):
        checks.append(("viewport_width_match", f"--viewport-width: {viewport_width}" in html_content, 10))
    if isinstance(viewport_height, int):
        checks.append(("viewport_height_match", f"--viewport-height: {viewport_height}" in html_content, 10))
    if isinstance(min_font_size_px, int):
        checks.append(("min_font_match", f"--min-font-size: {min_font_size_px}" in html_content, 10))

    total_weight = sum(weight for _, _, weight in checks)
    passed_weight = sum(weight for _, passed, weight in checks if passed)
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
    threshold = settings.qa_min_quality_score
    check_map = {name: passed for name, passed, _ in checks}
    failed_checks = [name for name, passed, _ in checks if not passed]

    hard_failures: list[str] = []
    lowered = html_content.lower()
    if "+100 score" in lowered and "requestanimationframe" not in lowered:
        hard_failures.append("trivial_score_button_template")
    if "addEventListener(\"click\")" in html_content and "keydown" not in lowered and "<canvas" not in lowered:
        hard_failures.append("click_only_interaction")

    # --- Quality Floor: 3D rendering engine required ---
    has_threejs = "three.js" in lowered or "three.module" in lowered or "three.min.js" in lowered
    has_webgl = "getcontext(\"webgl" in lowered or "getcontext('webgl" in lowered or "webglrenderer" in lowered
    if not has_threejs and not has_webgl:
        hard_failures.append("no_3d_rendering_engine")

    resolved_genre = resolve_genre_engine(
        genre_engine or genre or "",
        keyword=keyword or "",
    )
    genre_floor = get_genre_quality_floor(resolved_genre)
    min_fn_count = int(genre_floor.get("min_functions", 15) or 15)
    min_line_count = int(genre_floor.get("min_lines", 800) or 800)
    min_shader_count = int(genre_floor.get("min_shaders", 1) or 1)
    min_state_count = int(genre_floor.get("min_states", 2) or 2)

    # --- Quality Floor: minimum code complexity ---
    import re as _re
    function_count = len(_re.findall(r"\bfunction\s+\w+\s*\(", html_content))
    arrow_fn_count = len(_re.findall(r"\b(?:const|let|var)\s+\w+\s*=\s*(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>", html_content))
    total_fn_count = function_count + arrow_fn_count
    line_count = html_content.count("\n") + 1
    if total_fn_count < min_fn_count:
        hard_failures.append("code_complexity_too_low_fn_count")
    if line_count < min_line_count:
        hard_failures.append("code_complexity_too_low_line_count")

    shader_token_count = sum(
        lowered.count(token)
        for token in (
            "fragmentshader",
            "vertexshader",
            "shadermaterial",
            "glsl",
            "gl_position",
            "gl_fragcolor",
        )
    )
    if shader_token_count < min_shader_count:
        hard_failures.append("shader_complexity_too_low")

    state_token_count = sum(
        lowered.count(token)
        for token in (
            "state.",
            "gamestate",
            "switch(state",
            "state_machine",
            "mode ===",
            "mode===",
            "running",
            "restart",
            "game over",
            "overlay",
        )
    )
    if state_token_count < min_state_count:
        hard_failures.append("state_machine_complexity_too_low")

    # --- Quality Floor: shader presence (signal) ---
    has_shader = shader_token_count > 0
    check_map["has_custom_shader"] = has_shader
    check_map["quality_floor_min_functions"] = total_fn_count >= min_fn_count
    check_map["quality_floor_min_lines"] = line_count >= min_line_count
    check_map["quality_floor_min_shaders"] = shader_token_count >= min_shader_count
    check_map["quality_floor_min_states"] = state_token_count >= min_state_count

    if hard_failures:
        failed_checks.extend(hard_failures)
        for failure in hard_failures:
            check_map[failure] = False

    return QualityGateResult(
        ok=(score >= threshold) and not hard_failures,
        score=score,
        threshold=threshold,
        failed_checks=failed_checks,
        checks=check_map,
    )


_RACING_GENRE_ENGINES = {
    "f1_formula_circuit_3d",
    "webgl_three_runner",
    "lane_dodge_racer",
    "racing_3d",
}
_FLIGHT_GENRE_ENGINES = {
    "flight_sim_3d",
    "space_combat",
}


def _resolve_gameplay_profile(*, genre_engine_hint: str, genre_hint: str, keyword_hint: str) -> str:
    combined = f"{genre_hint} {keyword_hint}"
    if genre_engine_hint in _RACING_GENRE_ENGINES:
        return "racing"
    if genre_engine_hint in _FLIGHT_GENRE_ENGINES:
        return "flight"
    if any(token in combined for token in ("레이싱", "레이스", "racing", "race", "drift", "드리프트", "f1", "formula", "서킷")):
        return "racing"
    if any(token in combined for token in ("비행", "flight", "pilot", "aircraft", "dogfight", "cockpit")):
        return "flight"
    return "combat"


def evaluate_gameplay_gate(
    settings: Settings,
    html_content: str,
    *,
    design_spec: dict[str, Any] | None = None,
    genre: str | None = None,
    genre_engine: str | None = None,
    keyword: str | None = None,
) -> GameplayGateResult:
    spec = design_spec or {}
    lowered = html_content.lower()
    genre_hint = (genre or "").strip().casefold()
    genre_engine_hint = (genre_engine or "").strip().casefold()
    keyword_hint = (keyword or "").strip().casefold()
    gameplay_profile = _resolve_gameplay_profile(
        genre_engine_hint=genre_engine_hint,
        genre_hint=genre_hint,
        keyword_hint=keyword_hint,
    )

    checks: list[tuple[str, bool, int]] = [
        ("core_loop_tick", "requestanimationframe" in lowered and "update(" in lowered and "draw(" in lowered, 16),
        ("restart_loop", "game over" in lowered and "restart" in lowered, 10),
        ("input_depth", lowered.count("keydown") >= 1 and any(key in lowered for key in ("arrowup", "arrowdown", "space")), 12),
        ("risk_reward", any(token in lowered for token in ("boost", "combo", "score +=", "state.score +=")), 14),
        ("pacing_control", any(token in lowered for token in ("spawnrate", "enemy_spawn_rate", "difficulty", "speed")), 12),
        ("feedback_fx", any(token in lowered for token in ("shadowblur", "burst(", "particles", "screen")), 13),
        ("readability_guard", "safe-area" in lowered and "overflow-guard" in lowered, 10),
        ("progression_curve", any(token in lowered for token in ("difficultyscale", "run.level", "leveltimer", "adaptive")), 12),
        ("replay_loop", any(token in lowered for token in ("restartgame", "combo", "timeleft")), 10),
        ("failure_feedback", "overlaytext" in lowered and "endgame(" in lowered, 8),
    ]
    if gameplay_profile == "combat":
        checks.extend(
            [
                ("control_tuning_table", "control_presets" in lowered and "const control =" in lowered, 10),
                ("depth_pack_system", "depth_packs" in lowered and "active_depth_pack" in lowered, 10),
                ("miniboss_loop", "spawnminiboss" in lowered and "miniboss" in lowered, 10),
                ("progression_state_machine", "stepprogression(" in lowered and "state.run.level" in lowered, 10),
                ("postfx_pipeline", "drawpostfx" in lowered and "vignette" in lowered, 8),
                ("audio_feedback", "playsfx(" in lowered or "audiocontext" in lowered, 8),
                ("sprite_pack_usage", "sprite_profile" in lowered or "roundrect" in lowered, 8),
                ("mode_branching", lowered.count("config.mode") >= 2, 10),
                ("telegraph_or_counterplay", any(token in lowered for token in ("attackcooldown", "dashcooldown", "kind === \"elite\"", "lanefloat")), 10),
                (
                    "mechanical_depth",
                    sum(
                        1
                        for token in ("dash", "jump", "boost", "drift", "reload", "parry", "combo", "overtake", "checkpoint")
                        if token in lowered
                    )
                    >= 3,
                    14,
                ),
                (
                    "encounter_variety",
                    sum(1 for token in ("elite", "miniboss", "hazard", "wave", "spawnpattern", "kind ===") if token in lowered) >= 3,
                    12,
                ),
                (
                    "feedback_fidelity",
                    sum(1 for token in ("shake", "flash", "particles", "playsfx", "hit", "impact", "trail") if token in lowered) >= 4,
                    12,
                ),
            ]
        )
    elif gameplay_profile == "racing":
        checks.extend(
            [
                (
                    "racing_control_runtime",
                    any(token in lowered for token in ("steervelocity", "drift", "accel_rate", "brake_rate", "throttle")),
                    18,
                ),
                (
                    "racing_checkpoint_loop",
                    "checkpoint" in lowered and any(token in lowered for token in ("lap", "split", "overtake", "roadcurve")),
                    18,
                ),
                ("racing_track_rendering", any(token in lowered for token in ("roadcurve", "roadscroll", "renderwebglbackground(")), 14),
                ("racing_speed_feedback", any(token in lowered for token in ("boosttimer", "speed", "trail", "vignette")), 10),
                ("racing_pressure_pattern", any(token in lowered for token in ("hazard", "traffic", "opponent", "spawn")), 10),
            ]
        )
    else:
        checks.extend(
            [
                ("flight_control_runtime", all(token in lowered for token in ("pitch", "roll", "yaw", "throttle")), 18),
                ("flight_checkpoint_loop", "checkpointcombo" in lowered and "state.flight.speed" in lowered, 14),
                ("flight_hazard_loop", "kind === \"ring\"" in lowered and "kind === \"hazard\"" in lowered, 14),
                ("flight_speed_feedback", any(token in lowered for token in ("afterburner", "trail", "speed", "boost")), 10),
            ]
        )

    if any(token in genre_hint for token in ("racing", "레이싱", "drift", "드리프트")):
        checks.append(("racing_specific_mechanics", any(token in lowered for token in ("boosttimer", "roadcurve", "accel", "brake")), 10))
    if any(token in genre_hint for token in ("webgl", "three", "3d")):
        checks.append(("webgl_background_runtime", "getcontext(\"webgl\")" in lowered and "renderwebglbackground(" in lowered, 12))
    if any(token in genre_hint for token in ("shooter", "슈팅")):
        checks.append(("shooter_specific_mechanics", "firebullet" in lowered and "bullets" in lowered, 10))
        checks.append(("shooter_enemy_behaviors", any(token in lowered for token in ("charger", "elite", "orbit")), 8))
    if any(token in genre_hint for token in ("fighter", "격투", "brawler")):
        checks.append(("fighter_specific_mechanics", "performattack" in lowered and "attackcooldown" in lowered, 10))
    if any(token in genre_hint for token in ("로그라이크", "roguelike", "탑다운", "topdown")):
        checks.append(("roguelike_progression", any(token in lowered for token in ("run.level", "difficultyscale", "dashcooldown")), 10))
    if genre_engine_hint:
        checks.append(
            (
                "genre_engine_declared",
                f"config.mode === \"{genre_engine_hint}\"" in lowered or f"config.mode===\"{genre_engine_hint}\"" in lowered,
                10,
            )
        )
    if genre_engine_hint == "flight_sim_3d":
        checks.append(("flight_controls", all(token in lowered for token in ("pitch", "roll", "yaw", "throttle")), 16))
        checks.append(("flight_progression_loop", "checkpointcombo" in lowered and "state.flight.speed" in lowered, 12))
        checks.append(("flight_hazard_loop", "kind === \"ring\"" in lowered and "kind === \"hazard\"" in lowered, 12))
    if genre_engine_hint == "f1_formula_circuit_3d":
        checks.append(
            (
                "f1_analog_steering_runtime",
                "steervelocity" in lowered and "lanefloat" in lowered and "math.round(state.player.lane)" not in lowered,
                14,
            )
        )
        checks.append(("f1_lap_checkpoint_loop", "state.formula.lap" in lowered and "checkpoint" in lowered, 14))
        checks.append(("f1_brake_accel_loop", "accel_rate" in lowered and "brake_rate" in lowered, 10))
        checks.append(("f1_overtake_boost_loop", "overtakechain" in lowered and "boosttimer" in lowered, 10))
        checks.append(("f1_track_rendering", "roadcurve" in lowered and "roadscroll" in lowered, 8))
    if genre_engine_hint == "webgl_three_runner":
        checks.append(
            (
                "analog_steering_runtime",
                "steervelocity" in lowered and "math.round(state.player.lane)" not in lowered,
                12,
            )
        )

    text_overflow_policy = str(spec.get("text_overflow_policy", "")).strip()
    if text_overflow_policy:
        checks.append(
            (
                "style_contract_preserved",
                text_overflow_policy.casefold() in lowered and "assetpack" in lowered,
                8,
            )
        )

    total_weight = sum(weight for _, _, weight in checks)
    passed_weight = sum(weight for _, passed, weight in checks if passed)
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
    threshold = settings.qa_min_gameplay_score
    check_map = {name: passed for name, passed, _ in checks}
    failed_checks = [name for name, passed, _ in checks if not passed]
    hard_failures: list[str] = []

    if "requestanimationframe" not in lowered:
        hard_failures.append("missing_realtime_loop")
    declared_mode_matches = bool(
        genre_engine_hint
        and (f"config.mode === \"{genre_engine_hint}\"" in lowered or f"config.mode===\"{genre_engine_hint}\"" in lowered)
    )
    if genre_engine_hint and "config.mode" in lowered and not declared_mode_matches:
        hard_failures.append("genre_engine_mismatch")
    if gameplay_profile == "combat":
        if "spawnenemy(" not in lowered and "state.enemies.push" not in lowered:
            hard_failures.append("no_enemy_pressure")
        if lowered.count("score +=") <= 1 and "combo" not in lowered:
            hard_failures.append("flat_scoring_loop")
    elif gameplay_profile == "racing":
        if not any(token in lowered for token in ("steervelocity", "accel_rate", "brake_rate", "drift", "throttle")):
            hard_failures.append("racing_control_missing")
        if "checkpoint" not in lowered and "lap" not in lowered:
            hard_failures.append("racing_progression_missing")
    if "flight" in keyword_hint and genre_engine_hint != "flight_sim_3d":
        hard_failures.append("keyword_engine_mismatch_flight")
    fill_rect_count = lowered.count("fillrect(")
    shape_signal = sum(
        lowered.count(token)
        for token in ("drawsprite(", "beginpath(", "arc(", "ellipse(", "quadraticcurveto(", "beziercurveto(", "roundrect(")
    )
    if fill_rect_count >= 42 and shape_signal <= 14:
        hard_failures.append("geometry_variety_too_low")
    if genre_engine_hint == "flight_sim_3d":
        missing_flight_token = any(token not in lowered for token in ("state.flight", "checkpointcombo", "throttle"))
        if missing_flight_token:
            hard_failures.append("flight_mechanics_not_found")
    if genre_engine_hint == "webgl_three_runner" and "math.round(state.player.lane)" in lowered:
        hard_failures.append("quantized_lane_steering")
    if genre_engine_hint == "f1_formula_circuit_3d":
        missing_formula_token = any(
            token not in lowered
            for token in ("state.formula", "checkpoint", "overtakechain", "accel_rate", "brake_rate")
        )
        if missing_formula_token:
            hard_failures.append("f1_mechanics_not_found")
        if "math.round(state.player.lane)" in lowered:
            hard_failures.append("f1_quantized_steering")

    if hard_failures:
        failed_checks.extend(hard_failures)
        for failure in hard_failures:
            check_map[failure] = False

    return GameplayGateResult(
        ok=(score >= threshold) and not hard_failures,
        score=score,
        threshold=threshold,
        failed_checks=failed_checks,
        checks=check_map,
    )


def evaluate_visual_gate(
    settings: Settings,
    visual_metrics: dict[str, float] | None,
    *,
    genre_engine: str | None = None,
) -> QualityGateResult:
    metrics = visual_metrics or {}
    engine = (genre_engine or "").strip().casefold()
    luminance_std = float(metrics.get("luminance_std", 0.0))
    non_dark_ratio = float(metrics.get("non_dark_ratio", 0.0))
    color_bucket_count = float(metrics.get("color_bucket_count", 0.0))
    edge_energy = float(metrics.get("edge_energy", 0.0))
    motion_delta = float(metrics.get("motion_delta", 0.0))
    width = float(metrics.get("canvas_width", 0.0))
    height = float(metrics.get("canvas_height", 0.0))

    checks: list[tuple[str, bool, int]] = [
        ("canvas_size_present", width >= 640 and height >= 360, 10),
        ("visual_contrast", luminance_std >= 22.0, 20),
        ("color_diversity", color_bucket_count >= 22.0, 16),
        ("composition_balance", 0.08 <= non_dark_ratio <= 0.92, 12),
        ("edge_definition", edge_energy >= 0.025, 18),
        ("motion_presence", motion_delta >= 0.0012, 14),
        ("metrics_available", bool(metrics), 10),
        ("visual_cohesion", luminance_std >= 18.0 and edge_energy >= 0.02 and color_bucket_count >= 18.0, 12),
    ]
    if engine in {"webgl_three_runner", "flight_sim_3d"}:
        checks.append(("advanced_visual_density", color_bucket_count >= 28.0 and edge_energy >= 0.034, 12))

    total_weight = sum(weight for _, _, weight in checks)
    passed_weight = sum(weight for _, passed, weight in checks if passed)
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
    threshold = settings.qa_min_visual_score
    check_map = {name: passed for name, passed, _ in checks}
    failed_checks = [name for name, passed, _ in checks if not passed]
    hard_failures: list[str] = []

    if not metrics:
        hard_failures.append("visual_metrics_missing")
    if color_bucket_count < 10:
        hard_failures.append("visual_palette_too_flat")
    if edge_energy < 0.015:
        hard_failures.append("visual_shape_definition_too_low")

    if hard_failures:
        failed_checks.extend(hard_failures)
        for failure in hard_failures:
            check_map[failure] = False

    return QualityGateResult(
        ok=(score >= threshold) and not hard_failures,
        score=score,
        threshold=threshold,
        failed_checks=failed_checks,
        checks=check_map,
    )


def evaluate_artifact_contract(
    settings: Settings,
    artifact_manifest: dict[str, Any] | None,
    *,
    art_direction_contract: dict[str, Any] | None = None,
) -> ArtifactContractResult:
    manifest = artifact_manifest or {}
    art_contract = art_direction_contract or {}
    files = manifest.get("files")
    files_count = len(files) if isinstance(files, list) else 0
    bundle_kind = str(manifest.get("bundle_kind", "")).strip()
    modules = manifest.get("modules")
    module_count = len(modules) if isinstance(modules, list) else 0
    asset_manifest = manifest.get("asset_manifest")
    image_assets = 0
    policy_mode = ""
    policy_provider = ""
    policy_external_generation = None
    procedural_layer_count = 0
    mesh_layer_count = 0
    silhouette_set_count = 0
    fx_hook_count = 0
    material_profile_count = 0
    asset_pipeline_present = False
    asset_pipeline_automated = False
    asset_pipeline_variant_count = 0
    asset_pipeline_selected_variant = ""
    if isinstance(asset_manifest, dict):
        images = asset_manifest.get("images")
        if isinstance(images, dict):
            image_assets = len([value for value in images.values() if isinstance(value, str) and value.strip()])
        policy = asset_manifest.get("asset_policy")
        if isinstance(policy, dict):
            policy_mode = str(policy.get("mode", "")).strip()
            policy_provider = str(policy.get("provider", "")).strip()
            if isinstance(policy.get("external_image_generation"), bool):
                policy_external_generation = bool(policy.get("external_image_generation"))
        procedural_layers = asset_manifest.get("procedural_layers")
        if isinstance(procedural_layers, list):
            procedural_layer_count = len([value for value in procedural_layers if isinstance(value, str) and value.strip()])
        mesh_layers = asset_manifest.get("mesh_like_layers")
        if isinstance(mesh_layers, list):
            mesh_layer_count = len([value for value in mesh_layers if isinstance(value, str) and value.strip()])
        silhouette_sets = asset_manifest.get("silhouette_sets")
        if isinstance(silhouette_sets, list):
            silhouette_set_count = len([value for value in silhouette_sets if isinstance(value, str) and value.strip()])
        fx_hooks = asset_manifest.get("fx_hooks")
        if isinstance(fx_hooks, list):
            fx_hook_count = len([value for value in fx_hooks if isinstance(value, str) and value.strip()])
        material_profiles = asset_manifest.get("material_profiles")
        if isinstance(material_profiles, list):
            material_profile_count = len([value for value in material_profiles if isinstance(value, str) and value.strip()])
        pipeline_meta = asset_manifest.get("asset_pipeline")
        if isinstance(pipeline_meta, dict):
            asset_pipeline_present = True
            asset_pipeline_automated = bool(pipeline_meta.get("automated"))
            asset_pipeline_variant_count = int(pipeline_meta.get("variant_count", 0) or 0)
            asset_pipeline_selected_variant = str(pipeline_meta.get("selected_variant", "")).strip()
    contract_min_images = int(art_contract.get("min_image_assets", 5) or 5)
    contract_min_layers = int(art_contract.get("min_render_layers", 4) or 4)
    contract_min_hooks = int(art_contract.get("min_animation_hooks", 3) or 3)
    contract_min_procedural_layers = int(art_contract.get("min_procedural_layers", 3) or 3)
    runtime_hooks = manifest.get("runtime_hooks")
    runtime_hook_count = len(runtime_hooks) if isinstance(runtime_hooks, list) else 0

    checks: list[tuple[str, bool, int]] = [
        ("manifest_present", bool(manifest), 14),
        ("bundle_kind_hybrid_engine", bundle_kind == "hybrid_engine", 14),
        ("artifact_files_count", files_count >= 3, 10),
        ("image_assets_count", image_assets >= contract_min_images, 18),
        ("render_layers_count", module_count >= contract_min_layers, 16),
        ("animation_hooks_count", runtime_hook_count >= contract_min_hooks, 16),
        ("procedural_layers_count", procedural_layer_count >= contract_min_procedural_layers, 12),
        ("mesh_like_layers_count", mesh_layer_count >= 3, 10),
        ("silhouette_sets_count", silhouette_set_count >= 3, 8),
        ("fx_hooks_count", fx_hook_count >= 3, 8),
        ("material_profiles_count", material_profile_count >= 3, 8),
        ("policy_mode_procedural_threejs_first", policy_mode == "procedural_threejs_first", 8),
        ("policy_provider_present", bool(policy_provider), 6),
        ("policy_external_generation_disabled", policy_external_generation is False, 6),
        ("asset_pipeline_present", asset_pipeline_present, 8),
        ("asset_pipeline_automated", asset_pipeline_automated, 8),
        ("asset_pipeline_variant_count", asset_pipeline_variant_count >= 2, 8),
        ("asset_pipeline_selected_variant", bool(asset_pipeline_selected_variant), 4),
        ("art_direction_contract_present", bool(art_contract), 12),
        (
            "asset_density",
            image_assets >= 6
            and procedural_layer_count >= 3
            and module_count >= 4
            and mesh_layer_count >= 3
            and silhouette_set_count >= 3
            and fx_hook_count >= 3,
            12,
        ),
    ]

    total_weight = sum(weight for _, _, weight in checks)
    passed_weight = sum(weight for _, passed, weight in checks if passed)
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
    threshold = settings.qa_min_artifact_contract_score
    check_map = {name: passed for name, passed, _ in checks}
    failed_checks = [name for name, passed, _ in checks if not passed]
    hard_failures: list[str] = []

    if image_assets < max(3, contract_min_images - 1):
        hard_failures.append("insufficient_image_assets")
    if runtime_hook_count < max(2, contract_min_hooks - 1):
        hard_failures.append("insufficient_animation_hooks")
    if procedural_layer_count < max(2, contract_min_procedural_layers - 1):
        hard_failures.append("insufficient_procedural_layers")
    if bundle_kind != "hybrid_engine":
        hard_failures.append("unsupported_bundle_kind")
    if policy_mode != "procedural_threejs_first":
        hard_failures.append("asset_policy_mode_mismatch")
    if policy_external_generation is not False:
        hard_failures.append("external_image_generation_not_disabled")
    if not asset_pipeline_present:
        hard_failures.append("asset_pipeline_metadata_missing")
    if not asset_pipeline_automated:
        hard_failures.append("asset_pipeline_not_automated")
    if asset_pipeline_variant_count < 1:
        hard_failures.append("asset_pipeline_variant_count_invalid")

    if hard_failures:
        failed_checks.extend(hard_failures)
        for failure in hard_failures:
            check_map[failure] = False

    return ArtifactContractResult(
        ok=(score >= threshold) and not hard_failures,
        score=score,
        threshold=threshold,
        failed_checks=failed_checks,
        checks=check_map,
    )
