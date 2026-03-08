from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult


# --- Inline fallbacks for deleted modules (genre_engine, visual_contract) ---

def resolve_genre_engine(genre_or_engine: str, *, keyword: str = "") -> str:
    """Minimal genre engine resolver (inline fallback)."""
    combined = f"{genre_or_engine} {keyword}".strip().casefold()
    if any(t in combined for t in ("racing", "f1", "formula", "drift")):
        return "f1_formula_circuit_3d"
    if any(t in combined for t in ("flight", "space", "pilot", "dogfight")):
        return "space_combat"
    if any(t in combined for t in ("roguelike", "topdown", "dungeon")):
        return "topdown_roguelike_shooter"
    return "webgl_three_runner"


def get_genre_quality_floor(genre_engine: str) -> dict[str, int]:
    """Minimal genre quality floor (inline fallback)."""
    return {
        "min_functions": 15,
        "min_lines": 800,
        "min_shaders": 1,
        "min_states": 2,
    }


@dataclass
class _VisualContract:
    contrast_min: float = 0.03
    color_diversity_min: float = 8.0
    composition_non_dark_min: float = 0.05
    composition_non_dark_max: float = 0.95
    edge_energy_min: float = 0.005
    motion_delta_min: float = 0.001
    cohesion_contrast_min: float = 0.02
    cohesion_edge_min: float = 0.003
    cohesion_color_min: float = 6.0
    advanced_density_enabled: bool = False
    advanced_density_color_min: float = 12.0
    advanced_density_edge_min: float = 0.01


def resolve_visual_contract_profile(
    core_loop_type: str | None = None,
    runtime_engine_mode: str | None = None,
    contract_version: str = "v2",
    keyword: str = "",
) -> _VisualContract:
    """Minimal visual contract profile (inline fallback)."""
    return _VisualContract()


def evaluate_quality_contract(
    settings: Settings,
    html_content: str,
    *,
    design_spec: dict[str, Any] | None = None,
    genre: str | None = None,
    genre_engine: str | None = None,
    runtime_engine_mode: str | None = None,
    keyword: str | None = None,
    intent_contract: dict[str, Any] | None = None,
    synapse_contract: dict[str, Any] | None = None,
) -> QualityGateResult:
    _ = (intent_contract, synapse_contract)
    spec = design_spec or {}
    lowered = html_content.lower()
    overflow_policy_present = any(
        token in lowered
        for token in (
            "data-overflow-policy",
            "overflow-guard",
            "overflow:hidden",
            "overflow: hidden",
            "document.body.style.overflow",
        )
    )
    state_logic_present = any(
        token in lowered
        for token in (
            "game over",
            "overlay",
            "state.",
            "gamestate",
            "mode",
            "phase",
            "status",
            "restart",
            "reset",
            "retry",
        )
    )
    input_signal_present = any(
        token in lowered
        for token in (
            "keydown",
            "keyup",
            "pointerdown",
            "pointermove",
            "mousedown",
            "mousemove",
            "touchstart",
            "touchmove",
            "gamepad",
        )
    )

    checks: list[tuple[str, bool, int]] = [
        ("boot_flag", "window.__iis_game_boot_ok" in html_content, 20),
        ("viewport_meta", "<meta name=\"viewport\"" in html_content, 20),
        ("leaderboard_contract", "window.IISLeaderboard" in html_content, 20),
        ("overflow_guard", "overflow-guard" in html_content or "overflow:hidden" in lowered or "overflow: hidden" in lowered, 15),
        ("overflow_policy", overflow_policy_present, 10),
        ("safe_area", "--safe-area-padding" in html_content or "safe-area" in lowered, 15),
        ("canvas_present", "<canvas" in lowered, 20),
        ("game_loop_raf", "requestanimationframe" in lowered, 20),
        ("input_binding", input_signal_present, 15),
        ("game_state_logic", state_logic_present, 10),
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
    if "+100 score" in lowered and "requestanimationframe" not in lowered:
        hard_failures.append("trivial_score_button_template")
    if "addeventlistener(\"click\")" in lowered and not input_signal_present and "<canvas" not in lowered:
        hard_failures.append("click_only_interaction")

    # --- Runtime engine contract ---
    has_threejs = "three.js" in lowered or "three.module" in lowered or "three.min.js" in lowered
    has_webgl = "getcontext(\"webgl" in lowered or "getcontext('webgl" in lowered or "webglrenderer" in lowered
    has_phaser = "phaser.min.js" in lowered or "new phaser.game" in lowered or "class mainscene extends phaser.scene" in lowered
    normalized_engine_mode = str(runtime_engine_mode or "").strip().casefold()
    if normalized_engine_mode not in {"2d_phaser", "3d_three"}:
        if str(genre_engine or "").strip().casefold() in {"topdown_roguelike_shooter", "platformer_2d", "puzzle_2d"}:
            normalized_engine_mode = "2d_phaser"
        else:
            normalized_engine_mode = "3d_three"
    if normalized_engine_mode == "2d_phaser":
        if not has_phaser:
            hard_failures.append("engine_contract_2d_phaser_missing")
    else:
        if not has_threejs and not has_webgl:
            hard_failures.append("engine_contract_3d_three_missing")

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
    function_count = len(re.findall(r"\bfunction\s+\w+\s*\(", html_content))
    arrow_fn_count = len(re.findall(r"\b(?:const|let|var)\s+\w+\s*=\s*(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>", html_content))
    method_candidates = re.findall(r"(?m)^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*\{", html_content)
    reserved_words = {"if", "for", "while", "switch", "catch", "function"}
    method_count = sum(1 for name in method_candidates if name.casefold() not in reserved_words)
    total_fn_count = function_count + arrow_fn_count + method_count
    line_count = html_content.count("\n") + 1

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
        check_map["shader_complexity_too_low"] = False

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

    # --- Quality Floor: shader presence (signal) ---
    has_shader = shader_token_count > 0
    check_map["has_custom_shader"] = has_shader
    check_map["quality_floor_min_functions"] = total_fn_count >= min_fn_count
    check_map["quality_floor_min_lines"] = line_count >= min_line_count
    check_map["quality_floor_min_shaders"] = shader_token_count >= min_shader_count
    check_map["quality_floor_min_states"] = state_token_count >= min_state_count
    check_map["engine_contract_match"] = (
        has_phaser if normalized_engine_mode == "2d_phaser" else (has_threejs or has_webgl)
    )

    # --- Hard failures: only universal runtime-viability failures ---
    if "requestanimationframe" not in lowered:
        hard_failures.append("missing_realtime_loop")
    if not input_signal_present:
        hard_failures.append("input_reactivity_missing")
    if total_fn_count < 4:
        hard_failures.append("code_structure_too_shallow")
    if line_count < 120:
        hard_failures.append("code_structure_too_short")
    if state_token_count < 1:
        hard_failures.append("state_model_missing")

    if hard_failures:
        failed_checks.extend(hard_failures)
        for failure in hard_failures:
            check_map[failure] = False
        score = min(score, max(0, threshold - 5))

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


def _rows_as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


def _contract_required_tokens(
    *,
    intent_contract: dict[str, Any] | None,
    synapse_contract: dict[str, Any] | None,
    limit: int = 12,
) -> list[str]:
    synapse = synapse_contract if isinstance(synapse_contract, dict) else {}
    intent = intent_contract if isinstance(intent_contract, dict) else {}
    token_rows: list[str] = []
    token_rows.extend(_rows_as_str_list(synapse.get("required_mechanics")))
    token_rows.extend(_rows_as_str_list(synapse.get("required_progression")))
    token_rows.extend(_rows_as_str_list(intent.get("player_verbs")))
    token_rows.extend(_rows_as_str_list(intent.get("progression_loop")))
    deduped: list[str] = []
    for row in token_rows:
        for token in _extract_intent_tokens(row, limit=4):
            if token not in deduped:
                deduped.append(token)
            if len(deduped) >= limit:
                return deduped
    return deduped


def evaluate_gameplay_gate(
    settings: Settings,
    html_content: str,
    *,
    design_spec: dict[str, Any] | None = None,
    genre: str | None = None,
    genre_engine: str | None = None,
    keyword: str | None = None,
    intent_contract: dict[str, Any] | None = None,
    synapse_contract: dict[str, Any] | None = None,
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

    loop_signal = any(token in lowered for token in ("requestanimationframe", "setinterval(", "settimeout("))
    loop_cadence_signal = any(token in lowered for token in ("update(", "tick(", "step(", "loop(", "animate("))
    restart_signal = any(token in lowered for token in ("restart", "reset", "retry", "new run", "newrun", "start over", "startover"))
    input_signal = any(
        token in lowered
        for token in (
            "keydown",
            "keyup",
            "pointerdown",
            "pointermove",
            "mousedown",
            "mousemove",
            "touchstart",
            "touchmove",
            "gamepad",
        )
    )
    failure_signal = any(
        token in lowered
        for token in (
            "game over",
            "failed",
            "defeat",
            "crash",
            "destroyed",
            "hp <= 0",
            "health <= 0",
            "overlay",
        )
    )
    progression_signal = any(
        token in lowered
        for token in (
            "level",
            "wave",
            "checkpoint",
            "objective",
            "mission",
            "stage",
            "quest",
            "progress",
            "lap",
            "score +=",
            "state.score +=",
        )
    )

    checks: list[tuple[str, bool, int]] = [
        ("core_loop_tick", loop_signal and loop_cadence_signal, 16),
        ("restart_loop", restart_signal, 10),
        ("input_depth", input_signal and "addeventlistener" in lowered, 12),
        ("risk_reward", any(token in lowered for token in ("boost", "combo", "score +=", "state.score +=")), 14),
        ("pacing_control", any(token in lowered for token in ("spawnrate", "enemy_spawn_rate", "difficulty", "speed")), 12),
        ("feedback_fx", any(token in lowered for token in ("shadowblur", "burst(", "particles", "screen")), 13),
        (
            "readability_guard",
            any(token in lowered for token in ("safe-area", "overflow-guard", "data-overflow-policy", "overflow:hidden", "overflow: hidden")),
            10,
        ),
        ("progression_curve", progression_signal or any(token in lowered for token in ("difficultyscale", "run.level", "leveltimer", "adaptive")), 12),
        ("replay_loop", restart_signal or any(token in lowered for token in ("restartgame", "retry", "new run")), 10),
        ("failure_feedback", failure_signal or restart_signal, 8),
    ]

    advisory_checks: list[tuple[str, bool]] = []
    if gameplay_profile == "combat":
        advisory_checks.extend(
            [
                ("combat_mechanical_depth", sum(1 for token in ("dash", "combo", "aim", "attack", "upgrade", "xp") if token in lowered) >= 3),
                ("combat_encounter_variety", sum(1 for token in ("elite", "miniboss", "hazard", "wave", "spawnpattern") if token in lowered) >= 3),
            ]
        )
    elif gameplay_profile == "racing":
        advisory_checks.extend(
            [
                ("racing_control_runtime", any(token in lowered for token in ("steervelocity", "drift", "accel_rate", "brake_rate", "throttle"))),
                ("racing_checkpoint_loop", "checkpoint" in lowered and any(token in lowered for token in ("lap", "split", "overtake", "roadcurve"))),
            ]
        )
    else:
        advisory_checks.extend(
            [
                ("flight_control_runtime", all(token in lowered for token in ("pitch", "roll", "yaw", "throttle"))),
                ("flight_progression_loop", "checkpoint" in lowered or "checkpointcombo" in lowered),
            ]
        )

    if any(token in genre_hint for token in ("racing", "레이싱", "drift", "드리프트")):
        advisory_checks.append(("racing_specific_mechanics", any(token in lowered for token in ("boosttimer", "roadcurve", "accel", "brake"))))
    if any(token in genre_hint for token in ("webgl", "three", "3d")):
        advisory_checks.append(("webgl_background_runtime", "getcontext(\"webgl\")" in lowered or "webglrenderer" in lowered))
    if any(token in genre_hint for token in ("shooter", "슈팅")):
        advisory_checks.append(("shooter_specific_mechanics", "firebullet" in lowered and "bullets" in lowered))
    if any(token in genre_hint for token in ("fighter", "격투", "brawler")):
        advisory_checks.append(("fighter_specific_mechanics", "performattack" in lowered or "attackcooldown" in lowered))
    if any(token in genre_hint for token in ("로그라이크", "roguelike", "탑다운", "topdown")):
        advisory_checks.append(("roguelike_progression", any(token in lowered for token in ("run.level", "difficultyscale", "dashcooldown"))))
        advisory_checks.extend(
            [
                ("topdown_upgrade_pause", "physics.world.pause()" in lowered and "physics.world.resume()" in lowered),
                ("topdown_kill_fed_xp", "gainxp(" in lowered),
                ("topdown_arena_lock", "resolvedashtarget" in lowered and ("setcollideworldbounds(true)" in lowered or "world.setbounds" in lowered)),
                ("topdown_enemy_variety", "flanker" in lowered and "bruiser" in lowered),
            ]
        )
    if genre_engine_hint:
        advisory_checks.append(
            (
                "genre_engine_declared",
                f"config.mode === \"{genre_engine_hint}\"" in lowered or f"config.mode===\"{genre_engine_hint}\"" in lowered,
            )
        )
    if genre_engine_hint == "f1_formula_circuit_3d":
        advisory_checks.extend(
            [
                (
                    "f1_analog_steering_runtime",
                    "steervelocity" in lowered and "lanefloat" in lowered and "math.round(state.player.lane)" not in lowered,
                ),
                ("f1_lap_checkpoint_loop", "state.formula.lap" in lowered and "checkpoint" in lowered),
            ]
        )
    if genre_engine_hint == "webgl_three_runner":
        advisory_checks.append(("analog_steering_runtime", "steervelocity" in lowered and "math.round(state.player.lane)" not in lowered))

    text_overflow_policy = str(spec.get("text_overflow_policy", "")).strip()
    if text_overflow_policy:
        advisory_checks.append(
            (
                "style_contract_preserved",
                text_overflow_policy.casefold() in lowered and "assetpack" in lowered,
            )
        )

    total_weight = sum(weight for _, _, weight in checks)
    passed_weight = sum(weight for _, passed, weight in checks if passed)
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
    threshold = settings.qa_min_gameplay_score
    check_map = {name: passed for name, passed, _ in checks}
    failed_checks = [name for name, passed, _ in checks if not passed]
    for name, passed in advisory_checks:
        check_map[name] = passed
    hard_failures: list[str] = []

    required_contract_tokens = _contract_required_tokens(
        intent_contract=intent_contract,
        synapse_contract=synapse_contract,
    )
    matched_contract_tokens = [token for token in required_contract_tokens if token in lowered]
    if required_contract_tokens:
        contract_alignment_ok = _ratio(len(matched_contract_tokens), len(required_contract_tokens)) >= 0.24
        check_map["intent_mechanics_alignment"] = contract_alignment_ok
        if not contract_alignment_ok:
            hard_failures.append("intent_mechanics_unmet")
    else:
        check_map["intent_mechanics_alignment"] = True

    if not loop_signal:
        hard_failures.append("missing_realtime_loop")
    if not input_signal:
        hard_failures.append("input_reactivity_missing")
    if genre_engine_hint == "webgl_three_runner":
        if "math.round(state.player.lane)" in lowered:
            hard_failures.append("quantized_lane_steering")

    if hard_failures:
        failed_checks.extend(hard_failures)
        for failure in hard_failures:
            check_map[failure] = False
        score = min(score, max(0, threshold - 5))

    return GameplayGateResult(
        ok=(score >= threshold) and not hard_failures,
        score=score,
        threshold=threshold,
        failed_checks=failed_checks,
        checks=check_map,
    )


def evaluate_visual_gate(
    settings: Settings,
    visual_metrics: dict[str, Any] | None,
    *,
    genre_engine: str | None = None,
    runtime_engine_mode: str | None = None,
) -> QualityGateResult:
    def _metric_series(name: str) -> list[float]:
        values: list[float] = []
        primary = metrics.get(name)
        if isinstance(primary, (int, float)) and not isinstance(primary, bool):
            values.append(float(primary))
        samples = metrics.get(f"{name}_samples")
        if isinstance(samples, list):
            for row in samples:
                if isinstance(row, (int, float)) and not isinstance(row, bool):
                    values.append(float(row))
        return [value for value in values if value >= 0.0]

    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        middle = len(sorted_values) // 2
        if len(sorted_values) % 2 == 1:
            return sorted_values[middle]
        return (sorted_values[middle - 1] + sorted_values[middle]) / 2.0

    metrics = visual_metrics if isinstance(visual_metrics, dict) else {}
    contract = resolve_visual_contract_profile(
        core_loop_type=genre_engine,
        runtime_engine_mode=runtime_engine_mode,
        contract_version=getattr(settings, "visual_contract_version", "v2"),
    )
    luminance_samples = _metric_series("luminance_std")
    non_dark_samples = _metric_series("non_dark_ratio")
    color_samples = _metric_series("color_bucket_count")
    edge_samples = _metric_series("edge_energy")
    motion_samples = _metric_series("motion_delta")
    motion_p90_metric = metrics.get("motion_delta_p90")
    if isinstance(motion_p90_metric, (int, float)) and not isinstance(motion_p90_metric, bool):
        motion_samples.append(float(motion_p90_metric))

    luminance_std = _median(luminance_samples)
    non_dark_ratio = _median(non_dark_samples)
    color_bucket_count = _median(color_samples)
    edge_energy = _median(edge_samples)
    motion_delta = max(motion_samples) if motion_samples else 0.0
    motion_delta_p90 = 0.0
    if motion_samples:
        sorted_motion = sorted(motion_samples)
        p90_index = max(0, min(len(sorted_motion) - 1, int(round((len(sorted_motion) - 1) * 0.9))))
        motion_delta_p90 = sorted_motion[p90_index]
    motion_signal = max(motion_delta, motion_delta_p90)
    width = float(metrics.get("canvas_width", 0.0)) if isinstance(metrics.get("canvas_width"), (int, float)) else 0.0
    height = float(metrics.get("canvas_height", 0.0)) if isinstance(metrics.get("canvas_height"), (int, float)) else 0.0
    frame_probe_count = int(metrics.get("frame_probe_count", 0)) if isinstance(metrics.get("frame_probe_count"), (int, float)) else len(luminance_samples)

    contrast_weight = 20
    diversity_weight = 16
    edge_weight = 18
    motion_weight = 14
    if contract.advanced_density_enabled:
        contrast_weight = 18
        diversity_weight = 18
        edge_weight = 20
        motion_weight = 16

    checks: list[tuple[str, bool, int]] = [
        ("canvas_size_present", width >= 640 and height >= 360, 10),
        ("visual_contrast", luminance_std >= contract.contrast_min, contrast_weight),
        ("color_diversity", color_bucket_count >= contract.color_diversity_min, diversity_weight),
        ("composition_balance", contract.composition_non_dark_min <= non_dark_ratio <= contract.composition_non_dark_max, 12),
        ("edge_definition", edge_energy >= contract.edge_energy_min, edge_weight),
        ("motion_presence", motion_signal >= contract.motion_delta_min, motion_weight),
        ("metrics_available", bool(metrics), 10),
        (
            "visual_cohesion",
            luminance_std >= contract.cohesion_contrast_min
            and edge_energy >= contract.cohesion_edge_min
            and color_bucket_count >= contract.cohesion_color_min,
            12,
        ),
        ("multi_frame_probe", frame_probe_count >= 2, 8),
    ]
    if contract.advanced_density_enabled:
        checks.append(
            (
                "advanced_visual_density",
                color_bucket_count >= contract.advanced_density_color_min and edge_energy >= contract.advanced_density_edge_min,
                12,
            )
        )

    total_weight = sum(weight for _, _, weight in checks)
    passed_weight = sum(weight for _, passed, weight in checks if passed)
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
    threshold = settings.qa_min_visual_score
    check_map = {name: passed for name, passed, _ in checks}
    failed_checks = [name for name, passed, _ in checks if not passed]
    hard_failures: list[str] = []

    if not metrics:
        hard_failures.append("visual_metrics_missing")
    if frame_probe_count < 2:
        hard_failures.append("visual_probe_insufficient")
    if color_bucket_count < max(8.0, contract.color_diversity_min * 0.45):
        hard_failures.append("visual_palette_too_flat")
    if edge_energy < max(0.01, contract.edge_energy_min * 0.6):
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


_INTENT_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "game",
    "player",
    "mode",
    "loop",
    "intent",
    "contract",
    "요청",
    "게임",
    "플레이",
    "루프",
}

_TOKEN_PATTERN = re.compile(r"[a-z0-9가-힣]+", flags=re.IGNORECASE)


def _extract_intent_tokens(value: str, *, limit: int = 8) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_PATTERN.findall(str(value).casefold()):
        token = raw.strip().casefold()
        if len(token) < 3 or token in _INTENT_STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def _ratio(passed: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return max(0.0, min(1.0, passed / total))


def evaluate_intent_gate(
    html_content: str,
    *,
    intent_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    contract = intent_contract or {}
    lowered = html_content.casefold()

    fantasy_tokens = _extract_intent_tokens(str(contract.get("fantasy", "")))
    fantasy_hits = [token for token in fantasy_tokens if token in lowered]

    player_verbs = [
        str(item).strip().casefold()
        for item in (contract.get("player_verbs") or [])
        if str(item).strip()
    ]
    player_verb_hits = [verb for verb in player_verbs if verb in lowered]
    player_verbs_ok = _ratio(len(player_verb_hits), max(len(player_verbs), 1)) >= 0.34

    camera_tokens = _extract_intent_tokens(str(contract.get("camera_interaction", "")))
    camera_hits = [token for token in camera_tokens if token in lowered]
    camera_ok = _ratio(len(camera_hits), max(len(camera_tokens), 1)) >= 0.25

    progression_rows = [
        str(item).strip()
        for item in (contract.get("progression_loop") or [])
        if str(item).strip()
    ]
    progression_tokens: list[str] = []
    for row in progression_rows:
        progression_tokens.extend(_extract_intent_tokens(row, limit=4))
    progression_tokens = list(dict.fromkeys(progression_tokens))[:10]
    progression_hits = [token for token in progression_tokens if token in lowered]
    progression_ok = _ratio(len(progression_hits), max(len(progression_tokens), 1)) >= 0.3

    fail_restart_text = str(contract.get("fail_restart_loop", "")).casefold()
    fail_tokens = _extract_intent_tokens(fail_restart_text, limit=6)
    fail_hits = [token for token in fail_tokens if token in lowered]
    restart_signal_ok = any(token in lowered for token in ("restart", "reset", "retry", "game over", "fail"))
    fail_restart_ok = restart_signal_ok and (_ratio(len(fail_hits), max(len(fail_tokens), 1)) >= 0.25)
    fantasy_ratio_ok = _ratio(len(fantasy_hits), max(len(fantasy_tokens), 1)) >= 0.25
    fantasy_context_ok = player_verbs_ok and progression_ok and fail_restart_ok
    fantasy_ok = not fantasy_tokens or fantasy_ratio_ok or fantasy_context_ok

    non_negotiables = [
        str(item).strip()
        for item in (contract.get("non_negotiables") or [])
        if str(item).strip()
    ]
    non_negotiable_failures: list[str] = []
    non_negotiable_advisories: list[str] = []
    for item in non_negotiables:
        lowered_item = item.casefold()
        if lowered_item.startswith("avoid:"):
            banned = lowered_item.split(":", 1)[1].strip()
            if banned and banned in lowered:
                non_negotiable_failures.append(f"forbidden_present:{banned}")
        elif lowered_item == "preserve_requested_intent_without_generic_substitution":
            if "generic arcade" in lowered:
                non_negotiable_failures.append("generic_arcade_substitution")
        else:
            intent_tokens = _extract_intent_tokens(lowered_item, limit=4)
            if intent_tokens and not any(token in lowered for token in intent_tokens):
                non_negotiable_advisories.append(f"weak_signal:{item[:48]}")
    non_negotiables_ok = len(non_negotiable_failures) == 0

    checks = {
        "fantasy": fantasy_ok,
        "player_verbs": player_verbs_ok,
        "camera_interaction": camera_ok,
        "progression_loop": progression_ok,
        "fail_restart_loop": fail_restart_ok,
        "non_negotiables": non_negotiables_ok,
    }
    weights = {
        "fantasy": 22,
        "player_verbs": 20,
        "camera_interaction": 14,
        "progression_loop": 16,
        "fail_restart_loop": 18,
        "non_negotiables": 10,
    }
    score = sum(weight for key, weight in weights.items() if checks.get(key))
    threshold = 75
    failed_items = [key for key, passed in checks.items() if not passed]

    reason_by_item: dict[str, list[str]] = {
        "fantasy": [f"missing_tokens:{token}" for token in fantasy_tokens if token not in fantasy_hits][:5],
        "player_verbs": [f"missing_verb:{token}" for token in player_verbs if token not in player_verb_hits][:6],
        "camera_interaction": [f"missing_tokens:{token}" for token in camera_tokens if token not in camera_hits][:4],
        "progression_loop": [f"missing_tokens:{token}" for token in progression_tokens if token not in progression_hits][:6],
        "fail_restart_loop": [] if fail_restart_ok else ["restart_or_fail_signal_missing"],
        "non_negotiables": non_negotiable_failures[:8],
    }
    if non_negotiable_advisories:
        reason_by_item["non_negotiables_advisory"] = non_negotiable_advisories[:8]

    return {
        "ok": score >= threshold,
        "score": score,
        "threshold": threshold,
        "failed_items": failed_items,
        "checks": checks,
        "reason_by_item": {key: value for key, value in reason_by_item.items() if value},
    }
