from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult


def evaluate_quality_contract(
    settings: Settings,
    html_content: str,
    *,
    design_spec: dict[str, Any] | None = None,
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

    checks: list[tuple[str, bool, int]] = [
        ("core_loop_tick", "requestanimationframe" in lowered and "update(" in lowered and "draw(" in lowered, 16),
        ("restart_loop", "game over" in lowered and "restart" in lowered, 10),
        ("input_depth", lowered.count("keydown") >= 1 and any(key in lowered for key in ("arrowup", "arrowdown", "space")), 15),
        ("control_tuning_table", "control_presets" in lowered and "const control =" in lowered, 10),
        ("depth_pack_system", "depth_packs" in lowered and "active_depth_pack" in lowered, 10),
        ("miniboss_loop", "spawnminiboss" in lowered and "miniboss" in lowered, 10),
        ("relic_synergy_system", "relic_synergy_rules" in lowered and "applyrelicsynergy" in lowered, 10),
        ("risk_reward", any(token in lowered for token in ("boost", "combo", "score +=", "state.score +=")), 14),
        ("pacing_control", any(token in lowered for token in ("spawnrate", "enemy_spawn_rate", "difficulty", "speed")), 12),
        ("feedback_fx", any(token in lowered for token in ("shadowblur", "burst(", "particles", "screen")), 13),
        ("postfx_pipeline", "drawpostfx" in lowered and "vignette" in lowered, 8),
        ("audio_feedback", "playsfx(" in lowered or "audiocontext" in lowered, 8),
        ("sprite_pack_usage", "sprite_profile" in lowered or "roundrect" in lowered, 8),
        ("readability_guard", "safe-area" in lowered and "overflow-guard" in lowered, 10),
        ("mode_branching", lowered.count("config.mode") >= 2, 10),
        ("progression_curve", any(token in lowered for token in ("difficultyscale", "run.level", "leveltimer", "adaptive")), 12),
        ("replay_loop", any(token in lowered for token in ("restartgame", "combo", "timeleft")), 10),
        ("telegraph_or_counterplay", any(token in lowered for token in ("attackcooldown", "dashcooldown", "kind === \"elite\"", "lanefloat")), 10),
        ("failure_feedback", "overlaytext" in lowered and "endgame(" in lowered, 8),
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
    if "spawnenemy(" not in lowered and "state.enemies.push" not in lowered:
        hard_failures.append("no_enemy_pressure")
    if lowered.count("score +=") <= 1 and "combo" not in lowered:
        hard_failures.append("flat_scoring_loop")
    if genre_engine_hint and not (
        f"config.mode === \"{genre_engine_hint}\"" in lowered or f"config.mode===\"{genre_engine_hint}\"" in lowered
    ):
        hard_failures.append("genre_engine_mismatch")
    if "flight" in keyword_hint and genre_engine_hint != "flight_sim_3d":
        hard_failures.append("keyword_engine_mismatch_flight")
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
        ("policy_mode_procedural_threejs_first", policy_mode == "procedural_threejs_first", 8),
        ("policy_provider_present", bool(policy_provider), 6),
        ("policy_external_generation_disabled", policy_external_generation is False, 6),
        ("asset_pipeline_present", asset_pipeline_present, 8),
        ("asset_pipeline_automated", asset_pipeline_automated, 8),
        ("asset_pipeline_variant_count", asset_pipeline_variant_count >= 2, 8),
        ("asset_pipeline_selected_variant", bool(asset_pipeline_selected_variant), 4),
        ("art_direction_contract_present", bool(art_contract), 12),
        ("asset_density", image_assets >= 6 and procedural_layer_count >= 3 and module_count >= 4, 12),
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
