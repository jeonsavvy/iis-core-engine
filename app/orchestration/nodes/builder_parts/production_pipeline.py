from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.builder_parts.bundle import _extract_hybrid_bundle_from_inline_html
from app.orchestration.nodes.builder_parts.intent_contract import compute_intent_contract_hash
from app.orchestration.nodes.builder_parts.synapse_contract import compute_synapse_contract_hash
from app.orchestration.nodes.builder_parts.scaffold_builder import build_scaffold_html
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import BuildArtifactPayload, DesignSpecPayload, GDDPayload, IntentContractPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus
from app.services.quality_types import GameplayGateResult, PlayabilityGateResult, QualityGateResult, SmokeCheckResult
from app.services.shared_generation_contract import compute_shared_generation_contract_hash
from app.services.vertex_text_utils import compile_generated_artifact
from app.services.visual_contract import resolve_visual_contract_profile


@dataclass(frozen=True)
class ProductionBuildResult:
    build_artifact: BuildArtifactPayload
    selected_generation_meta: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _ArtifactAssessment:
    html: str
    quality: QualityGateResult
    gameplay: GameplayGateResult
    playability: PlayabilityGateResult
    smoke: SmokeCheckResult
    visual: QualityGateResult
    builder_score: float
    placeholder_heavy: bool
    placeholder_score: float
    runtime_warning_penalty: float
    runtime_warning_codes: list[str]
    intent_gate_report: dict[str, Any]


def _coerce_int(value: object, *, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return int(float(text))
        except Exception:
            return fallback
    return fallback


def _normalize_core_loop_type(core_loop_type: str) -> str:
    normalized = str(core_loop_type).strip()
    if normalized.casefold() == "request_faithful_generic":
        return "comic_action_brawler_3d"
    return normalized or "comic_action_brawler_3d"


def _evaluate_visual_or_fallback(
    *,
    deps: NodeDependencies,
    visual_metrics: dict[str, object] | None,
    core_loop_type: str,
    runtime_engine_mode: str,
) -> QualityGateResult:
    evaluate_visual = getattr(deps.quality_service, "evaluate_visual_gate", None)
    if callable(evaluate_visual):
        try:
            evaluated = evaluate_visual(
                visual_metrics,
                genre_engine=core_loop_type,
                runtime_engine_mode=runtime_engine_mode,
            )
        except TypeError:
            evaluated = evaluate_visual(
                visual_metrics,
                genre_engine=core_loop_type,
            )
        if isinstance(evaluated, QualityGateResult):
            return evaluated
    has_metrics = bool(visual_metrics)
    fallback_score = 70 if has_metrics else 45
    return QualityGateResult(
        ok=has_metrics,
        score=fallback_score,
        threshold=50,
        failed_checks=[] if has_metrics else ["visual_metrics_missing"],
        checks={"visual_fallback": has_metrics},
    )


def _evaluate_playability_gate(*, smoke: SmokeCheckResult) -> PlayabilityGateResult:
    reason = str(smoke.reason or "").strip().casefold()
    raw_warnings = [str(item).strip() for item in (smoke.non_fatal_warnings or []) if str(item).strip()]
    warning_codes = _critical_runtime_warning_codes(raw_warnings)
    fail_reasons = list(dict.fromkeys(warning_codes))
    if reason.startswith("playwright_error"):
        fail_reasons.append("playwright_error")
    elif reason.startswith("qa_exception"):
        fail_reasons.append("qa_exception")
    elif reason == "runtime_console_error":
        fail_reasons.append(reason)
    if smoke.ok is False and reason and reason not in fail_reasons:
        fail_reasons.append(reason)
    score = max(0, 100 - (len(fail_reasons) * 18))
    return PlayabilityGateResult(
        ok=len(fail_reasons) == 0,
        score=score,
        fail_reasons=fail_reasons,
        warning_codes=warning_codes,
    )


def _compose_builder_score(
    *,
    quality_score: int,
    gameplay_score: int,
    visual_score: int,
    smoke_ok: bool,
    placeholder_score: float,
    runtime_warning_penalty: float,
) -> float:
    score = (quality_score * 0.32) + (gameplay_score * 0.46) + (visual_score * 0.22)
    if not smoke_ok:
        score -= 22.0
    score -= min(24.0, placeholder_score * 24.0)
    score -= runtime_warning_penalty
    return round(max(0.0, score), 2)


def _estimate_placeholder_risk(html_content: str) -> tuple[bool, float]:
    lowered = html_content.lower()
    fill_rect_count = lowered.count("fillrect(")
    draw_sprite_count = lowered.count("drawsprite(")
    path_count = sum(
        lowered.count(token)
        for token in (
            "beginpath(",
            "arc(",
            "ellipse(",
            "quadraticcurveto(",
            "beziercurveto(",
            "roundrect(",
            "lineTo(".lower(),
        )
    )
    gradient_count = lowered.count("createlineargradient(") + lowered.count("createradialgradient(")
    unique_hex_colors = len(set(match.group(0).lower() for match in re.finditer(r"#[0-9a-f]{6}", lowered)))
    if fill_rect_count <= 0:
        return False, 0.0

    geometric_signal = (path_count + draw_sprite_count + gradient_count + unique_hex_colors) / max(fill_rect_count, 1)
    raw_risk = 1.0 - min(1.0, geometric_signal / 1.8)
    heavy = fill_rect_count >= 20 and raw_risk >= 0.55 and draw_sprite_count <= 4
    if "placeholder rectangle-only visuals" in lowered:
        heavy = True
        raw_risk = max(raw_risk, 0.85)
    return heavy, round(max(0.0, min(raw_risk, 1.0)), 3)


def _critical_runtime_warning_codes(warnings: list[str] | None) -> list[str]:
    if not warnings:
        return []
    critical_tokens = {
        "overlay_game_over_visible",
        "immediate_zero_hp_state",
        "zero_hp_state",
        "timer_static_with_overlay",
        "timer_not_progressing",
        "start_gate_visible",
        "manual_start_interaction_required",
        "runtime_layout_scroll_overflow",
        "hud_jargon_visible",
        "early_session_game_over",
    }
    normalized = [str(item).strip().casefold() for item in warnings if str(item).strip()]
    return [code for code in normalized if code in critical_tokens]


def _runtime_warning_penalty(warnings: list[str] | None) -> float:
    if not warnings:
        return 0.0
    penalties = {
        "overlay_game_over_visible": 14.0,
        "immediate_zero_hp_state": 16.0,
        "zero_hp_state": 10.0,
        "timer_static_with_overlay": 12.0,
        "timer_not_progressing": 9.0,
        "start_gate_visible": 8.0,
        "manual_start_interaction_required": 8.0,
        "runtime_layout_scroll_overflow": 6.0,
        "hud_jargon_visible": 8.0,
        "early_session_game_over": 14.0,
    }
    score = 0.0
    for token in warnings:
        code = str(token).strip().casefold()
        score += penalties.get(code, 0.0)
    return round(min(28.0, score), 2)


def _metric_value(metrics: dict[str, object], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _evaluate_generation_checklist(
    *,
    assessment: _ArtifactAssessment,
    visual_contract: dict[str, Any],
    shared_generation_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    quality_checks = assessment.quality.checks if isinstance(assessment.quality.checks, dict) else {}
    gameplay_checks = assessment.gameplay.checks if isinstance(assessment.gameplay.checks, dict) else {}
    visual_metrics = assessment.smoke.visual_metrics if isinstance(assessment.smoke.visual_metrics, dict) else {}
    runtime_probe = assessment.smoke.runtime_probe_summary if isinstance(assessment.smoke.runtime_probe_summary, dict) else {}
    runtime_warnings = {
        str(code).strip().casefold()
        for code in (assessment.smoke.non_fatal_warnings or [])
        if str(code).strip()
    }
    has_visual_metrics = bool(visual_metrics)
    visual_contrast_ok = (
        _metric_value(visual_metrics, "luminance_std") >= float(visual_contract.get("contrast_min", 0.0) or 0.0)
        if has_visual_metrics
        else bool(assessment.visual.ok)
    )
    visual_diversity_ok = (
        _metric_value(visual_metrics, "color_bucket_count") >= float(visual_contract.get("color_diversity_min", 0.0) or 0.0)
        if has_visual_metrics
        else bool(assessment.visual.ok)
    )
    visual_edge_ok = (
        _metric_value(visual_metrics, "edge_energy") >= float(visual_contract.get("edge_energy_min", 0.0) or 0.0)
        if has_visual_metrics
        else bool(assessment.visual.ok)
    )
    visual_motion_ok = (
        _metric_value(visual_metrics, "motion_delta") >= float(visual_contract.get("motion_delta_min", 0.0) or 0.0)
        if has_visual_metrics
        else bool(assessment.visual.ok)
    )

    required_map: dict[str, bool]
    if isinstance(shared_generation_contract, dict):
        raw_required_map = shared_generation_contract.get("checklist")
        if isinstance(raw_required_map, dict):
            required_map = {str(key): bool(value) for key, value in raw_required_map.items()}
        else:
            required_map = {}
    else:
        required_map = {}
    input_reaction_ok = (
        bool(runtime_probe.get("input_reaction_ok", False))
        and "input_reaction_missing" not in runtime_warnings
        and "input_probe_keypress_failed" not in runtime_warnings
    )
    if not runtime_probe:
        input_reaction_ok = True

    checks: dict[str, bool] = {
        "boot_flag": bool(quality_checks.get("boot_flag", True)),
        "leaderboard_contract": bool(quality_checks.get("leaderboard_contract", True)),
        "realtime_loop": bool(quality_checks.get("game_loop_raf", True)),
        "input_reaction": input_reaction_ok,
        "state_transition": bool(quality_checks.get("game_state_logic", True))
        and "timer_not_progressing" not in runtime_warnings
        and "timer_static_with_overlay" not in runtime_warnings,
        "restart_loop": bool(gameplay_checks.get("restart_loop", True)),
        "visual_contrast": visual_contrast_ok,
        "visual_diversity": visual_diversity_ok,
        "visual_edge": visual_edge_ok,
        "visual_motion": visual_motion_ok,
    }

    failed_required: list[str] = []
    for key, passed in checks.items():
        required = bool(required_map.get(key, True))
        if required and not passed:
            failed_required.append(key)

    return {
        "checks": checks,
        "required": {key: bool(required_map.get(key, True)) for key in checks.keys()},
        "failed_required_checks": failed_required,
        "ok": len(failed_required) == 0,
    }


def _is_vertex_resource_exhausted(*values: str) -> bool:
    combined = " ".join(str(value or "").casefold() for value in values)
    return any(
        token in combined
        for token in (
            "resource_exhausted",
            "resourceexhausted",
            "resource exhausted",
            "429",
            "quota",
            "rate limit",
            "too many requests",
        )
    )


def _build_asset_files_index(
    *,
    runtime_asset_manifest: dict[str, Any] | None,
    asset_bank_files: list[dict[str, str]],
) -> dict[str, str]:
    index: dict[str, str] = {}
    manifest = runtime_asset_manifest if isinstance(runtime_asset_manifest, dict) else {}
    images = manifest.get("images")
    if isinstance(images, dict):
        for key, value in images.items():
            key_text = str(key).strip()
            value_text = str(value).strip()
            if key_text and value_text:
                index[key_text] = value_text
    for row in asset_bank_files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path", "")).strip()
        if not path or "/" not in path:
            continue
        filename = path.rsplit("/", 1)[-1]
        stem = filename.split(".", 1)[0].strip()
        if stem and stem not in index:
            index[stem] = f"./{filename}"
    return index


def _preflight_selection_score(assessment: _ArtifactAssessment) -> float:
    gate_bonus = 0.0
    if assessment.quality.ok:
        gate_bonus += 8.0
    if assessment.gameplay.ok:
        gate_bonus += 10.0
    if assessment.visual.ok:
        gate_bonus += 8.0
    if assessment.playability.ok and assessment.smoke.ok:
        gate_bonus += 10.0
    return round(float(assessment.builder_score) + gate_bonus, 3)


def _should_prefer_fixed_candidate(*, raw: _ArtifactAssessment, fixed: _ArtifactAssessment) -> bool:
    raw_score = _preflight_selection_score(raw)
    fixed_score = _preflight_selection_score(fixed)
    if fixed_score > raw_score + 0.15:
        return True
    if fixed.visual.score > raw.visual.score and fixed.playability.ok:
        return True
    if (not raw.visual.ok) and fixed.visual.ok:
        return True
    return False


def _classify_blocking_reasons(reasons: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "visual": [],
        "runtime": [],
        "intent": [],
        "gameplay": [],
        "quality": [],
        "codegen": [],
        "other": [],
    }

    for row in reasons:
        token = str(row).strip()
        lowered = token.casefold()
        target = "other"
        if lowered.startswith("intent:") or lowered.startswith("intent_") or lowered == "intent_gate_unmet":
            target = "intent"
        elif lowered.startswith("codegen_") or lowered.startswith("codegen:") or lowered.startswith("codegen_reason:") or lowered.startswith("codegen_error:"):
            target = "codegen"
        elif lowered.startswith("runtime_") or lowered in {
            "runtime_smoke_failed",
            "builder_playability_unmet",
            "input_reactivity_missing",
            "missing_realtime_loop",
            "restart_loop",
            "core_loop_tick",
        }:
            target = "runtime"
        elif lowered.startswith("visual_") or lowered in {
            "visual_gate_unmet",
            "visual_contrast",
            "color_diversity",
            "edge_definition",
            "motion_presence",
            "composition_balance",
            "visual_cohesion",
        }:
            target = "visual"
        elif lowered.startswith("gameplay_") or lowered == "gameplay_gate_unmet":
            target = "gameplay"
        elif lowered.startswith("quality_") or lowered == "quality_gate_unmet":
            target = "quality"
        groups[target].append(token)

    return {key: value for key, value in groups.items() if value}


def _assess_artifact_quality(
    *,
    deps: NodeDependencies,
    html_content: str,
    design_spec: dict[str, Any],
    genre: str,
    core_loop_type: str,
    runtime_engine_mode: str,
    keyword: str,
    artifact_files: list[dict[str, str]],
    slug: str,
    intent_contract: dict[str, Any] | None = None,
    synapse_contract: dict[str, Any] | None = None,
) -> _ArtifactAssessment:
    evaluate_quality = getattr(deps.quality_service, "evaluate_quality_contract")
    try:
        quality = evaluate_quality(
            html_content,
            design_spec=design_spec,
            genre=genre,
            genre_engine=core_loop_type,
            runtime_engine_mode=runtime_engine_mode,
            keyword=keyword,
            intent_contract=intent_contract if isinstance(intent_contract, dict) else None,
            synapse_contract=synapse_contract if isinstance(synapse_contract, dict) else None,
        )
    except TypeError:
        quality = evaluate_quality(html_content, design_spec=design_spec)
    try:
        gameplay = deps.quality_service.evaluate_gameplay_gate(
            html_content,
            design_spec=design_spec,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=keyword,
            intent_contract=intent_contract if isinstance(intent_contract, dict) else None,
            synapse_contract=synapse_contract if isinstance(synapse_contract, dict) else None,
        )
    except TypeError:
        gameplay = deps.quality_service.evaluate_gameplay_gate(
            html_content,
            design_spec=design_spec,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=keyword,
        )
    smoke = deps.quality_service.run_smoke_check(
        html_content,
        artifact_files=artifact_files,
        entrypoint_path=f"games/{slug}/index.html",
    )
    playability = _evaluate_playability_gate(smoke=smoke)
    visual = _evaluate_visual_or_fallback(
        deps=deps,
        visual_metrics=smoke.visual_metrics,
        core_loop_type=core_loop_type,
        runtime_engine_mode=runtime_engine_mode,
    )
    runtime_warning_codes = _critical_runtime_warning_codes(smoke.non_fatal_warnings)
    runtime_warning_penalty = _runtime_warning_penalty(runtime_warning_codes)
    placeholder_heavy, placeholder_score = _estimate_placeholder_risk(html_content)
    evaluate_intent = getattr(deps.quality_service, "evaluate_intent_gate", None)
    if callable(evaluate_intent):
        intent_gate_report = evaluate_intent(
            html_content,
            intent_contract=intent_contract if isinstance(intent_contract, dict) else None,
        )
    else:
        intent_gate_report = {
            "ok": True,
            "score": 100,
            "threshold": 75,
            "failed_items": [],
            "checks": {"intent_gate_unavailable": True},
        }
    score = _compose_builder_score(
        quality_score=quality.score,
        gameplay_score=gameplay.score,
        visual_score=visual.score,
        smoke_ok=smoke.ok,
        placeholder_score=placeholder_score,
        runtime_warning_penalty=runtime_warning_penalty,
    )
    return _ArtifactAssessment(
        html=html_content,
        quality=quality,
        gameplay=gameplay,
        playability=playability,
        smoke=smoke,
        visual=visual,
        builder_score=score,
        placeholder_heavy=placeholder_heavy,
        placeholder_score=placeholder_score,
        runtime_warning_penalty=runtime_warning_penalty,
        runtime_warning_codes=runtime_warning_codes,
        intent_gate_report=intent_gate_report,
    )


def _build_intent_prompt_fragment(intent_contract: dict[str, Any] | None) -> str:
    contract = intent_contract if isinstance(intent_contract, dict) else {}
    fantasy = str(contract.get("fantasy", "")).strip()
    camera_interaction = str(contract.get("camera_interaction", "")).strip()
    fail_restart_loop = str(contract.get("fail_restart_loop", "")).strip()
    player_verbs = [str(item).strip() for item in (contract.get("player_verbs") or []) if str(item).strip()]
    progression_loop = [str(item).strip() for item in (contract.get("progression_loop") or []) if str(item).strip()]
    non_negotiables = [str(item).strip() for item in (contract.get("non_negotiables") or []) if str(item).strip()]
    rows: list[str] = []
    if fantasy:
        rows.append(f"Fantasy: {fantasy}")
    if player_verbs:
        rows.append(f"Player verbs: {', '.join(player_verbs[:8])}")
    if camera_interaction:
        rows.append(f"Camera/Interaction: {camera_interaction}")
    if progression_loop:
        rows.append("Progression loop: " + " -> ".join(progression_loop[:6]))
    if fail_restart_loop:
        rows.append(f"Fail/Restart loop: {fail_restart_loop}")
    if non_negotiables:
        rows.append(f"Non-negotiables: {', '.join(non_negotiables[:8])}")
    if not rows:
        return "Intent contract missing. Preserve the user request exactly without generic substitution."
    return "Intent contract:\n" + "\n".join(f"- {row}" for row in rows)


def _build_synapse_prompt_fragment(synapse_contract: dict[str, Any] | None) -> str:
    contract = synapse_contract if isinstance(synapse_contract, dict) else {}
    runtime_contract = contract.get("runtime_contract")
    runtime_rows = runtime_contract if isinstance(runtime_contract, dict) else {}
    engine_mode = str(runtime_rows.get("engine_mode", "")).strip()
    required_mechanics = [
        str(item).strip()
        for item in (contract.get("required_mechanics") or [])
        if str(item).strip()
    ]
    required_progression = [
        str(item).strip()
        for item in (contract.get("required_progression") or [])
        if str(item).strip()
    ]
    required_visual = [
        str(item).strip()
        for item in (contract.get("required_visual_signals") or [])
        if str(item).strip()
    ]
    non_negotiables = [
        str(item).strip()
        for item in (contract.get("non_negotiables") or [])
        if str(item).strip()
    ]

    rows: list[str] = []
    if engine_mode:
        rows.append(f"Engine mode: {engine_mode}")
    if required_mechanics:
        rows.append(f"Required mechanics: {', '.join(required_mechanics[:10])}")
    if required_progression:
        rows.append("Required progression: " + " -> ".join(required_progression[:8]))
    if required_visual:
        rows.append(f"Required visual signals: {', '.join(required_visual[:8])}")
    if non_negotiables:
        rows.append(f"Non-negotiables: {', '.join(non_negotiables[:8])}")
    if not rows:
        return "Synapse contract missing. Keep all stage outputs aligned to user intent."
    return "Synapse contract:\n" + "\n".join(f"- {row}" for row in rows)


def compute_intent_contract_hash_from_map(intent_contract: dict[str, Any] | None) -> str:
    if not isinstance(intent_contract, dict) or not intent_contract:
        return "missing"
    try:
        typed: IntentContractPayload = IntentContractPayload.model_validate(intent_contract)
    except Exception:
        return "invalid"
    return str(compute_intent_contract_hash(typed))


def _build_scaffold_first_production_artifact(
    *,
    state: PipelineState,
    deps: NodeDependencies,
    gdd: GDDPayload,
    design_spec: DesignSpecPayload,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    core_loop_type: str,
    runtime_engine_mode: str,
    asset_pack: dict[str, Any],
    asset_bank_files: list[dict[str, str]],
    runtime_asset_manifest: dict[str, Any],
    memory_hint: str = "",
    memory_tokens: list[str] | None = None,
    request_capability_hint: str = "",
    generated_genre_directive: str = "",
    intent_contract: dict[str, Any] | None = None,
    synapse_contract: dict[str, Any] | None = None,
    shared_generation_contract: dict[str, Any] | None = None,
) -> ProductionBuildResult:
    design_spec_dump = design_spec.model_dump()
    rebuild_feedback_hint = ""
    rebuild_feedback_tokens: list[str] = []

    normalized_memory_hint = memory_hint.strip()
    normalized_request_capability_hint = request_capability_hint.strip()
    normalized_generated_genre_directive = generated_genre_directive.strip()
    memory_feedback_tokens = [str(item).strip() for item in (memory_tokens or []) if str(item).strip()]
    combined_feedback_hint = " ".join(
        chunk
        for chunk in (
            normalized_request_capability_hint,
            normalized_generated_genre_directive,
            normalized_memory_hint,
        )
        if chunk
    ).strip()

    scaffold_html = build_scaffold_html(
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        viewport_width=design_spec.viewport_width,
        viewport_height=design_spec.viewport_height,
        safe_area_padding=design_spec.safe_area_padding,
        min_font_size_px=design_spec.min_font_size_px,
        text_overflow_policy=design_spec.text_overflow_policy,
        core_loop_type=core_loop_type,
        runtime_engine_mode=runtime_engine_mode,
        asset_pack=asset_pack,
    )
    intent_prompt = _build_intent_prompt_fragment(intent_contract)
    intent_contract_hash = compute_intent_contract_hash_from_map(intent_contract)
    synapse_prompt = _build_synapse_prompt_fragment(synapse_contract)
    synapse_contract_hash = compute_synapse_contract_hash(synapse_contract)
    shared_generation_contract_hash = compute_shared_generation_contract_hash(shared_generation_contract)
    effective_variation_hint = (
        f"single_pass_generation | {combined_feedback_hint}\n{intent_prompt}\n{synapse_prompt}\nShared contract hash: {shared_generation_contract_hash}"
        if combined_feedback_hint
        else f"single_pass_generation\n{intent_prompt}\n{synapse_prompt}\nShared contract hash: {shared_generation_contract_hash}"
    )

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.DEVELOPER,
        message=f"Scaffold-first generation started (iteration={state['build_iteration']}).",
        metadata={
            "iteration": state["build_iteration"],
            "core_loop_type": core_loop_type,
            "runtime_engine_mode": runtime_engine_mode,
            "asset_pack": asset_pack["name"],
            "generation_engine_version": "scaffold_v3",
            "generation_passes": 1,
            "rebuild_feedback_hint_applied": False,
            "visual_feedback_hint_applied": False,
            "memory_hint_applied": bool(normalized_memory_hint),
            "request_capability_hint_applied": bool(normalized_request_capability_hint),
            "generated_genre_directive_applied": bool(normalized_generated_genre_directive),
            "memory_feedback_tokens": memory_feedback_tokens,
            "qa_mode": "verify_only",
            "intent_contract_hash": intent_contract_hash,
            "synapse_contract_hash": synapse_contract_hash,
            "shared_generation_contract_hash": shared_generation_contract_hash,
        },
    )

    asset_files_index = _build_asset_files_index(
        runtime_asset_manifest=runtime_asset_manifest,
        asset_bank_files=asset_bank_files,
    )
    codegen_result = deps.vertex_service.generate_codegen_candidate_artifact(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        objective=gdd.objective,
        core_loop_type=core_loop_type,
        runtime_engine_mode=runtime_engine_mode,
        variation_hint=effective_variation_hint,
        design_spec=design_spec_dump,
        asset_pack=asset_pack,
        asset_manifest=runtime_asset_manifest,
        asset_files_index=asset_files_index,
        html_content=scaffold_html,
        intent_contract=intent_contract if isinstance(intent_contract, dict) else {},
        synapse_contract=synapse_contract if isinstance(synapse_contract, dict) else {},
        shared_generation_contract=shared_generation_contract if isinstance(shared_generation_contract, dict) else {},
    )
    raw_generated_html = str(codegen_result.payload.get("raw_artifact_html", "")).strip()
    generated_html = str(codegen_result.payload.get("artifact_html", "")).strip()
    generation_source = str(codegen_result.meta.get("generation_source", "stub")).strip().lower()
    generation_reason = str(codegen_result.meta.get("reason", "")).strip()
    generation_error = str(codegen_result.meta.get("vertex_error", "")).strip()
    generation_validation_failures = [
        str(item).strip()
        for item in (codegen_result.meta.get("validation_failures") or [])
        if str(item).strip()
    ]
    codegen_available = bool(generated_html) and generation_source == "vertex"
    initial_generation_reason = generation_reason
    initial_generation_error = generation_error
    initial_generation_validation_failures = list(generation_validation_failures)
    recovery_attempted = False
    recovery_success = False
    recovery_enabled = False
    recovery_meta: dict[str, Any] = {
        "generation_source": "disabled",
        "reason": "single_pass_only",
        "recovery_enabled": recovery_enabled,
    }
    strict_vertex_only = bool(getattr(deps.vertex_service.settings, "strict_vertex_only", True))
    allow_stub_fallback = bool(getattr(deps.vertex_service.settings, "allow_stub_fallback", False))
    deterministic_fallback_enabled = False
    deterministic_fallback_used = False
    deterministic_fallback_meta: dict[str, Any] = {"reason": "disabled_single_pass"}

    final_html = generated_html if codegen_available and generated_html else scaffold_html
    preflight_report: dict[str, Any] = {
        "enabled": bool(getattr(deps.vertex_service.settings, "builder_visual_precheck_enabled", True)),
        "selection_reason": "generated_default" if codegen_available else "scaffold_default",
    }

    scaffold_assessment = _assess_artifact_quality(
        deps=deps,
        html_content=scaffold_html,
        design_spec=design_spec_dump,
        genre=genre,
        core_loop_type=core_loop_type,
        runtime_engine_mode=runtime_engine_mode,
        keyword=state["keyword"],
        artifact_files=asset_bank_files,
        slug=slug,
        intent_contract=intent_contract,
        synapse_contract=synapse_contract,
    )
    final_assessment: _ArtifactAssessment
    compile_meta_for_report = codegen_result.meta.get("runtime_compiler") if isinstance(codegen_result.meta, dict) else {}
    if codegen_available and bool(getattr(deps.vertex_service.settings, "builder_visual_precheck_enabled", True)):
        raw_candidate_html = raw_generated_html or generated_html
        raw_assessment = _assess_artifact_quality(
            deps=deps,
            html_content=raw_candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            core_loop_type=core_loop_type,
            runtime_engine_mode=runtime_engine_mode,
            keyword=state["keyword"],
            artifact_files=asset_bank_files,
            slug=slug,
            intent_contract=intent_contract,
            synapse_contract=synapse_contract,
        )
        fixed_candidate_html, fixed_compile_meta = compile_generated_artifact(
            raw_candidate_html,
            asset_manifest=runtime_asset_manifest if isinstance(runtime_asset_manifest, dict) else None,
            asset_files_index=asset_files_index,
            visual_precheck_enabled=bool(getattr(deps.vertex_service.settings, "builder_visual_precheck_enabled", True)),
            deterministic_visual_fix=bool(getattr(deps.vertex_service.settings, "builder_deterministic_visual_fix", True)),
        )
        fixed_assessment = _assess_artifact_quality(
            deps=deps,
            html_content=fixed_candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            core_loop_type=core_loop_type,
            runtime_engine_mode=runtime_engine_mode,
            keyword=state["keyword"],
            artifact_files=asset_bank_files,
            slug=slug,
            intent_contract=intent_contract,
            synapse_contract=synapse_contract,
        )
        prefer_fixed = _should_prefer_fixed_candidate(raw=raw_assessment, fixed=fixed_assessment)
        if prefer_fixed:
            final_html = fixed_candidate_html
            final_assessment = fixed_assessment
            preflight_report["selection_reason"] = "fixed_candidate_better"
        else:
            final_html = raw_candidate_html
            final_assessment = raw_assessment
            preflight_report["selection_reason"] = "raw_candidate_kept"
        compile_meta_for_report = fixed_compile_meta
        preflight_report.update(
            {
                "raw": {
                    "quality": raw_assessment.quality.score,
                    "gameplay": raw_assessment.gameplay.score,
                    "visual": raw_assessment.visual.score,
                    "playability": raw_assessment.playability.score,
                    "smoke_ok": raw_assessment.smoke.ok,
                    "builder": raw_assessment.builder_score,
                },
                "fixed": {
                    "quality": fixed_assessment.quality.score,
                    "gameplay": fixed_assessment.gameplay.score,
                    "visual": fixed_assessment.visual.score,
                    "playability": fixed_assessment.playability.score,
                    "smoke_ok": fixed_assessment.smoke.ok,
                    "builder": fixed_assessment.builder_score,
                },
                "applied_transforms": fixed_compile_meta.get("transforms_applied", [])
                if isinstance(fixed_compile_meta, dict)
                else [],
                "asset_usage_count": (
                    fixed_compile_meta.get("asset_usage_count")
                    if isinstance(fixed_compile_meta, dict)
                    else 0
                ),
                "runtime_compiler": fixed_compile_meta if isinstance(fixed_compile_meta, dict) else {},
            }
        )
    else:
        final_assessment = _assess_artifact_quality(
            deps=deps,
            html_content=final_html,
            design_spec=design_spec_dump,
            genre=genre,
            core_loop_type=core_loop_type,
            runtime_engine_mode=runtime_engine_mode,
            keyword=state["keyword"],
            artifact_files=asset_bank_files,
            slug=slug,
            intent_contract=intent_contract,
            synapse_contract=synapse_contract,
        )
    visual_contract = resolve_visual_contract_profile(
        core_loop_type=core_loop_type,
        runtime_engine_mode=runtime_engine_mode,
        keyword=state["keyword"],
        contract_version=getattr(deps.vertex_service.settings, "visual_contract_version", "v2"),
    ).as_dict()
    generation_checklist_report = _evaluate_generation_checklist(
        assessment=final_assessment,
        visual_contract=visual_contract,
        shared_generation_contract=shared_generation_contract if isinstance(shared_generation_contract, dict) else None,
    )

    quality_floor_score = _coerce_int(
        getattr(deps.vertex_service.settings, "builder_quality_floor_score", 82),
        fallback=82,
    )
    quality_floor_score = max(0, min(100, quality_floor_score))
    quality_floor_enforced = bool(getattr(deps.vertex_service.settings, "builder_quality_floor_enforced", True))
    quality_floor_fail_reasons: list[str] = []
    if not codegen_available:
        quality_floor_fail_reasons.append("codegen_generation_failed")
        if generation_reason:
            quality_floor_fail_reasons.append(f"codegen_reason:{generation_reason}")
        if generation_error:
            quality_floor_fail_reasons.append(f"codegen_error:{generation_error[:120]}")
        for token in generation_validation_failures[:6]:
            quality_floor_fail_reasons.append(f"codegen_missing:{token}")
    if codegen_available:
        if not final_assessment.smoke.ok:
            quality_floor_fail_reasons.append("runtime_smoke_failed")
        if not final_assessment.playability.ok:
            quality_floor_fail_reasons.append("builder_playability_unmet")
            quality_floor_fail_reasons.extend(final_assessment.playability.fail_reasons)
        if not final_assessment.quality.ok:
            quality_floor_fail_reasons.append("quality_gate_unmet")
            quality_floor_fail_reasons.extend(final_assessment.quality.failed_checks[:8])
        if not final_assessment.gameplay.ok:
            quality_floor_fail_reasons.append("gameplay_gate_unmet")
            quality_floor_fail_reasons.extend(final_assessment.gameplay.failed_checks[:8])
        if not final_assessment.visual.ok:
            quality_floor_fail_reasons.append("visual_gate_unmet")
            quality_floor_fail_reasons.extend(final_assessment.visual.failed_checks[:8])
        if not bool(final_assessment.intent_gate_report.get("ok", False)):
            quality_floor_fail_reasons.append("intent_gate_unmet")
            intent_failed_items = final_assessment.intent_gate_report.get("failed_items")
            if isinstance(intent_failed_items, list):
                quality_floor_fail_reasons.extend(
                    f"intent:{str(item).strip()}"
                    for item in intent_failed_items[:8]
                    if str(item).strip()
                )
        if final_assessment.builder_score < float(quality_floor_score):
            quality_floor_fail_reasons.append("builder_quality_floor_unmet")
        if final_assessment.placeholder_heavy:
            quality_floor_fail_reasons.append("placeholder_visual_detected")
        if final_assessment.runtime_warning_codes:
            quality_floor_fail_reasons.append("runtime_liveness_warnings_detected")
        if not bool(generation_checklist_report.get("ok", False)):
            quality_floor_fail_reasons.append("generation_checklist_unmet")
            failed_required_checks = generation_checklist_report.get("failed_required_checks")
            if isinstance(failed_required_checks, list):
                quality_floor_fail_reasons.extend(
                    f"checklist:{str(item).strip()}"
                    for item in failed_required_checks[:10]
                    if str(item).strip()
                )
    quality_floor_fail_reasons = list(dict.fromkeys(quality_floor_fail_reasons))
    blocking_reason_groups = _classify_blocking_reasons(quality_floor_fail_reasons)
    quality_floor_passed = len(quality_floor_fail_reasons) == 0
    vertex_resource_exhausted_retryable = (not codegen_available) and _is_vertex_resource_exhausted(
        generation_reason,
        generation_error,
    )

    artifact_files: list[dict[str, str]] | None = None
    artifact_manifest: dict[str, object] | None = None
    hybrid_bundle = _extract_hybrid_bundle_from_inline_html(
        slug=slug,
        inline_html=final_html,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
    )
    if not hybrid_bundle:
        fallback_files = [
            {
                "path": f"games/{slug}/index.html",
                "content": final_html,
                "content_type": "text/html; charset=utf-8",
            },
            *asset_bank_files,
        ]
        fallback_manifest = {
            "schema_version": 1,
            "entrypoint": f"games/{slug}/index.html",
            "files": [row["path"] for row in fallback_files],
            "bundle_kind": "hybrid_engine",
            "asset_manifest": runtime_asset_manifest if isinstance(runtime_asset_manifest, dict) else {},
        }
        hybrid_bundle = (fallback_files, fallback_manifest)
    if hybrid_bundle:
        artifact_files, extracted_manifest = hybrid_bundle
        artifact_manifest = dict(extracted_manifest)
        artifact_manifest["genre_engine"] = core_loop_type
        artifact_manifest["asset_pack"] = asset_pack["name"]

    build_artifact = BuildArtifactPayload(
        game_slug=slug,
        game_name=title,
        game_genre=genre,
        artifact_path=f"games/{slug}/index.html",
        artifact_html=final_html,
        entrypoint_path=f"games/{slug}/index.html",
        artifact_files=artifact_files,
        artifact_manifest=artifact_manifest,
    )

    quality_gate_report = {
        "quality": {
            "ok": final_assessment.quality.ok,
            "score": final_assessment.quality.score,
            "threshold": final_assessment.quality.threshold,
            "failed_checks": final_assessment.quality.failed_checks,
        },
        "gameplay": {
            "ok": final_assessment.gameplay.ok,
            "score": final_assessment.gameplay.score,
            "threshold": final_assessment.gameplay.threshold,
            "failed_checks": final_assessment.gameplay.failed_checks,
        },
        "visual": {
            "ok": final_assessment.visual.ok,
            "score": final_assessment.visual.score,
            "threshold": final_assessment.visual.threshold,
            "failed_checks": final_assessment.visual.failed_checks,
        },
        "playability": {
            "ok": final_assessment.playability.ok,
            "score": final_assessment.playability.score,
            "fail_reasons": final_assessment.playability.fail_reasons,
        },
        "smoke": {
            "ok": final_assessment.smoke.ok,
            "reason": final_assessment.smoke.reason,
            "fatal_errors": final_assessment.smoke.fatal_errors,
            "non_fatal_warnings": final_assessment.smoke.non_fatal_warnings,
        },
        "intent": final_assessment.intent_gate_report,
        "visual_metrics": final_assessment.smoke.visual_metrics or {},
        "visual_contract": visual_contract,
        "generation_checklist_report": generation_checklist_report,
    }

    selected_generation_meta = dict(codegen_result.meta or {})
    if isinstance(compile_meta_for_report, dict) and compile_meta_for_report:
        selected_generation_meta["runtime_compiler"] = compile_meta_for_report
    codegen_usage = (
        selected_generation_meta.get("usage")
        if isinstance(selected_generation_meta.get("usage"), dict)
        else codegen_result.meta.get("usage")
        if isinstance(codegen_result.meta, dict) and isinstance(codegen_result.meta.get("usage"), dict)
        else {}
    )

    metadata = {
        "builder_strategy": "scaffold_first_codegen_v3",
        "generation_engine_version": "scaffold_v3",
        "runtime_engine_mode": runtime_engine_mode,
        "artifact_file_count": len(build_artifact.artifact_files or []),
        "codegen_enabled": True,
        "codegen_generation_attempts": 1,
        "codegen_recovery_enabled": recovery_enabled,
        "codegen_recovery_attempted": recovery_attempted,
        "codegen_recovery_success": recovery_success,
        "codegen_initial_reason": initial_generation_reason,
        "codegen_initial_error": initial_generation_error,
        "codegen_initial_validation_failures": initial_generation_validation_failures,
        "codegen_recovery_meta": recovery_meta,
        "deterministic_fallback_enabled": deterministic_fallback_enabled,
        "deterministic_fallback_used": deterministic_fallback_used,
        "deterministic_fallback_meta": deterministic_fallback_meta,
        "effective_codegen_passes_per_candidate": 1,
        "selected_candidate_index": 1,
        "selected_candidate_score": float(final_assessment.builder_score),
        "final_quality_score": final_assessment.quality.score,
        "final_gameplay_score": final_assessment.gameplay.score,
        "playability_score": final_assessment.playability.score,
        "playability_passed": final_assessment.playability.ok and final_assessment.smoke.ok,
        "playability_fail_reasons": final_assessment.playability.fail_reasons,
        "final_visual_score": final_assessment.visual.score,
        "final_builder_quality_score": final_assessment.builder_score,
        "final_placeholder_heavy": final_assessment.placeholder_heavy,
        "final_placeholder_score": final_assessment.placeholder_score,
        "final_runtime_warning_penalty": final_assessment.runtime_warning_penalty,
        "final_runtime_warning_codes": final_assessment.runtime_warning_codes,
        "quality_floor_score": quality_floor_score,
        "quality_floor_enforced": quality_floor_enforced,
        "quality_floor_passed": quality_floor_passed,
        "quality_floor_fail_reasons": quality_floor_fail_reasons,
        "blocking_reason_groups": blocking_reason_groups,
        "blocking_reasons_normalized": [
            f"{group}:{token}"
            for group, rows in blocking_reason_groups.items()
            for token in rows
        ],
        "visual_contract": visual_contract,
        "visual_profile_id": str(visual_contract.get("profile_id", "")).strip() or None,
        "visual_metrics": final_assessment.smoke.visual_metrics or {},
        "generation_checklist_report": generation_checklist_report,
        "builder_preflight_report": preflight_report,
        "runtime_compiler": compile_meta_for_report if isinstance(compile_meta_for_report, dict) else {},
        "asset_usage_report": {
            "asset_usage_count": (
                compile_meta_for_report.get("asset_usage_count", 0)
                if isinstance(compile_meta_for_report, dict)
                else 0
            ),
            "required_asset_keys": (
                compile_meta_for_report.get("required_asset_keys", [])
                if isinstance(compile_meta_for_report, dict)
                else []
            ),
            "used_asset_keys": (
                compile_meta_for_report.get("used_asset_keys", [])
                if isinstance(compile_meta_for_report, dict)
                else []
            ),
        },
        "vertex_resource_exhausted_retryable": vertex_resource_exhausted_retryable,
        "quality_gate_report": quality_gate_report,
        "intent_gate_report": final_assessment.intent_gate_report,
        "blocking_reasons": quality_floor_fail_reasons,
        "rebuild_feedback_hint_applied": bool(rebuild_feedback_hint),
        "rebuild_feedback_tokens": rebuild_feedback_tokens,
        "memory_hint_applied": bool(normalized_memory_hint),
        "request_capability_hint_applied": bool(normalized_request_capability_hint),
        "generated_genre_directive_applied": bool(normalized_generated_genre_directive),
        "memory_tokens": memory_feedback_tokens,
        "intent_contract": intent_contract if isinstance(intent_contract, dict) else {},
        "intent_contract_hash": intent_contract_hash,
        "synapse_contract": synapse_contract if isinstance(synapse_contract, dict) else {},
        "synapse_contract_hash": synapse_contract_hash,
        "shared_generation_contract": shared_generation_contract if isinstance(shared_generation_contract, dict) else {},
        "shared_generation_contract_hash": shared_generation_contract_hash,
        "strict_vertex_only": strict_vertex_only,
        "allow_stub_fallback": allow_stub_fallback,
        "fallback_blocked": not allow_stub_fallback,
        "codegen_usage": codegen_usage,
        "usage": codegen_usage,
        "model": str(selected_generation_meta.get("model", "")).strip() or None,
        "runtime_guard": {
            "chosen": "single_pass",
            "reason": final_assessment.smoke.reason,
            "probes": [
                {
                    "label": "scaffold_baseline",
                    "smoke_ok": scaffold_assessment.smoke.ok,
                    "quality_score": scaffold_assessment.quality.score,
                    "gameplay_score": scaffold_assessment.gameplay.score,
                    "playability_score": scaffold_assessment.playability.score,
                },
                {
                    "label": "generated",
                    "smoke_ok": final_assessment.smoke.ok,
                    "quality_score": final_assessment.quality.score,
                    "gameplay_score": final_assessment.gameplay.score,
                    "playability_score": final_assessment.playability.score,
                },
            ],
            "refinement": [],
        },
        "final_smoke_ok": final_assessment.smoke.ok,
        "final_smoke_reason": final_assessment.smoke.reason,
        "substrate_id": "scaffold",
        "camera_model": "generated",
        "interaction_model": "generated",
    }

    return ProductionBuildResult(
        build_artifact=build_artifact,
        selected_generation_meta=selected_generation_meta,
        metadata=metadata,
    )


def build_production_artifact(
    *,
    state: PipelineState,
    deps: NodeDependencies,
    gdd: GDDPayload,
    design_spec: DesignSpecPayload,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    core_loop_type: str,
    runtime_engine_mode: str,
    asset_pack: dict[str, Any],
    asset_bank_files: list[dict[str, str]],
    runtime_asset_manifest: dict[str, Any],
    memory_hint: str = "",
    memory_tokens: list[str] | None = None,
    request_capability_hint: str = "",
    generated_genre_directive: str = "",
    intent_contract: dict[str, Any] | None = None,
    synapse_contract: dict[str, Any] | None = None,
    shared_generation_contract: dict[str, Any] | None = None,
) -> ProductionBuildResult:
    core_loop_type = _normalize_core_loop_type(core_loop_type)
    normalized_runtime_engine_mode = str(runtime_engine_mode or "").strip() or "3d_three"
    return _build_scaffold_first_production_artifact(
        state=state,
        deps=deps,
        gdd=gdd,
        design_spec=design_spec,
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        core_loop_type=core_loop_type,
        runtime_engine_mode=normalized_runtime_engine_mode,
        asset_pack=asset_pack,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
        memory_hint=memory_hint,
        memory_tokens=memory_tokens,
        request_capability_hint=request_capability_hint,
        generated_genre_directive=generated_genre_directive,
        intent_contract=intent_contract,
        synapse_contract=synapse_contract,
        shared_generation_contract=shared_generation_contract,
    )
