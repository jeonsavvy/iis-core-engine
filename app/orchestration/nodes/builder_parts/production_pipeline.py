from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.builder_parts.bundle import _extract_hybrid_bundle_from_inline_html
from app.orchestration.nodes.builder_parts.scaffold_builder import build_scaffold_html
from app.orchestration.nodes.builder_parts.genre_engine import resolve_genre_engine, get_genre_reference_prompt
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import BuildArtifactPayload, DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus
from app.services.quality_types import GameplayGateResult, PlayabilityGateResult, QualityGateResult, SmokeCheckResult


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
    visual_metrics: dict[str, float] | None,
    core_loop_type: str,
) -> QualityGateResult:
    evaluate_visual = getattr(deps.quality_service, "evaluate_visual_gate", None)
    if callable(evaluate_visual):
        evaluated = evaluate_visual(visual_metrics, genre_engine=core_loop_type)
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


def _assess_artifact_quality(
    *,
    deps: NodeDependencies,
    html_content: str,
    design_spec: dict[str, Any],
    genre: str,
    core_loop_type: str,
    keyword: str,
    artifact_files: list[dict[str, str]],
    slug: str,
) -> _ArtifactAssessment:
    evaluate_quality = getattr(deps.quality_service, "evaluate_quality_contract")
    try:
        quality = evaluate_quality(
            html_content,
            design_spec=design_spec,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=keyword,
        )
    except TypeError:
        quality = evaluate_quality(html_content, design_spec=design_spec)
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
    )
    runtime_warning_codes = _critical_runtime_warning_codes(smoke.non_fatal_warnings)
    runtime_warning_penalty = _runtime_warning_penalty(runtime_warning_codes)
    placeholder_heavy, placeholder_score = _estimate_placeholder_risk(html_content)
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
    )


def _build_codegen_recovery_hint(*, failed_requirements: list[str]) -> str:
    requirement_prompts = {
        "html_document": "Return one complete HTML document with <html>, <head>, <body>.",
        "boot_flag": "Set window.__iis_game_boot_ok = true after runtime boot completes.",
        "leaderboard_contract": "Define window.IISLeaderboard contract object in global scope.",
        "realtime_loop": "Implement requestAnimationFrame-based realtime update loop.",
        "canvas_or_render_runtime": "Create playable canvas runtime (<canvas> or createElement('canvas') / WebGL renderer).",
    }
    hints = [
        requirement_prompts[item]
        for item in failed_requirements
        if item in requirement_prompts
    ]
    if not hints:
        return (
            "Structural recovery required. Return full playable HTML artifact with boot flag, leaderboard contract, "
            "requestAnimationFrame game loop, and active canvas runtime."
        )
    return "Structural recovery required. " + " ".join(hints)


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
    asset_pack: dict[str, Any],
    asset_bank_files: list[dict[str, str]],
    runtime_asset_manifest: dict[str, Any],
    memory_hint: str = "",
    memory_tokens: list[str] | None = None,
    request_capability_hint: str = "",
    generated_genre_directive: str = "",
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
        asset_pack=asset_pack,
    )
    genre_engine = resolve_genre_engine(genre, state["keyword"])
    genre_ref_prompt = get_genre_reference_prompt(genre_engine)
    effective_variation_hint = (
        f"single_pass_generation | {combined_feedback_hint}\n{genre_ref_prompt}"
        if combined_feedback_hint
        else f"single_pass_generation\n{genre_ref_prompt}"
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
        },
    )

    codegen_result = deps.vertex_service.generate_codegen_candidate_artifact(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        objective=gdd.objective,
        core_loop_type=core_loop_type,
        variation_hint=effective_variation_hint,
        design_spec=design_spec_dump,
        asset_pack=asset_pack,
        html_content=scaffold_html,
    )
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
    recovery_meta: dict[str, Any] = {}
    recovery_failures: list[str] = []
    if not codegen_available:
        recovery_attempted = True
        recovery_hint = _build_codegen_recovery_hint(failed_requirements=generation_validation_failures)
        recovery_variation_hint = f"{effective_variation_hint}\n{recovery_hint}"
        recovery_result = deps.vertex_service.generate_codegen_candidate_artifact(
            keyword=state["keyword"],
            title=title,
            genre=genre,
            objective=gdd.objective,
            core_loop_type=core_loop_type,
            variation_hint=recovery_variation_hint,
            design_spec=design_spec_dump,
            asset_pack=asset_pack,
            html_content=scaffold_html,
        )
        recovery_html = str(recovery_result.payload.get("artifact_html", "")).strip()
        recovery_source = str(recovery_result.meta.get("generation_source", "stub")).strip().lower()
        recovery_reason = str(recovery_result.meta.get("reason", "")).strip()
        recovery_error = str(recovery_result.meta.get("vertex_error", "")).strip()
        recovery_validation_failures = [
            str(item).strip()
            for item in (recovery_result.meta.get("validation_failures") or [])
            if str(item).strip()
        ]
        recovery_success = bool(recovery_html) and recovery_source == "vertex"
        recovery_failures = recovery_validation_failures
        recovery_meta = {
            "generation_source": recovery_source,
            "reason": recovery_reason,
            "vertex_error": recovery_error,
            "validation_failures": recovery_validation_failures,
        }
        if recovery_success:
            codegen_result = recovery_result
            generated_html = recovery_html
            generation_source = recovery_source
            generation_reason = recovery_reason
            generation_error = recovery_error
            generation_validation_failures = recovery_validation_failures
            codegen_available = True

    final_html = generated_html if generated_html else scaffold_html

    scaffold_assessment = _assess_artifact_quality(
        deps=deps,
        html_content=scaffold_html,
        design_spec=design_spec_dump,
        genre=genre,
        core_loop_type=core_loop_type,
        keyword=state["keyword"],
        artifact_files=asset_bank_files,
        slug=slug,
    )
    final_assessment = _assess_artifact_quality(
        deps=deps,
        html_content=final_html,
        design_spec=design_spec_dump,
        genre=genre,
        core_loop_type=core_loop_type,
        keyword=state["keyword"],
        artifact_files=asset_bank_files,
        slug=slug,
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
        if recovery_attempted and not recovery_success:
            quality_floor_fail_reasons.append("codegen_recovery_failed")
            recovery_reason = str(recovery_meta.get("reason", "")).strip()
            recovery_error = str(recovery_meta.get("vertex_error", "")).strip()
            if recovery_reason:
                quality_floor_fail_reasons.append(f"codegen_recovery_reason:{recovery_reason}")
            if recovery_error:
                quality_floor_fail_reasons.append(f"codegen_recovery_error:{recovery_error[:120]}")
        if generation_reason:
            quality_floor_fail_reasons.append(f"codegen_reason:{generation_reason}")
        if generation_error:
            quality_floor_fail_reasons.append(f"codegen_error:{generation_error[:120]}")
        for token in (generation_validation_failures or recovery_failures)[:6]:
            quality_floor_fail_reasons.append(f"codegen_missing:{token}")
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
    if final_assessment.builder_score < float(quality_floor_score):
        quality_floor_fail_reasons.append("builder_quality_floor_unmet")
    if final_assessment.placeholder_heavy:
        quality_floor_fail_reasons.append("placeholder_visual_detected")
    if final_assessment.runtime_warning_codes:
        quality_floor_fail_reasons.append("runtime_liveness_warnings_detected")
    quality_floor_fail_reasons = list(dict.fromkeys(quality_floor_fail_reasons))
    quality_floor_passed = len(quality_floor_fail_reasons) == 0

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
    }

    metadata = {
        "builder_strategy": "scaffold_first_codegen_v3",
        "generation_engine_version": "scaffold_v3",
        "artifact_file_count": len(build_artifact.artifact_files or []),
        "codegen_enabled": True,
        "codegen_generation_attempts": 2 if recovery_attempted else 1,
        "codegen_recovery_attempted": recovery_attempted,
        "codegen_recovery_success": recovery_success,
        "codegen_initial_reason": initial_generation_reason,
        "codegen_initial_error": initial_generation_error,
        "codegen_initial_validation_failures": initial_generation_validation_failures,
        "codegen_recovery_meta": recovery_meta,
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
        "quality_gate_report": quality_gate_report,
        "blocking_reasons": quality_floor_fail_reasons,
        "rebuild_feedback_hint_applied": bool(rebuild_feedback_hint),
        "rebuild_feedback_tokens": rebuild_feedback_tokens,
        "memory_hint_applied": bool(normalized_memory_hint),
        "request_capability_hint_applied": bool(normalized_request_capability_hint),
        "generated_genre_directive_applied": bool(normalized_generated_genre_directive),
        "memory_tokens": memory_feedback_tokens,
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
        selected_generation_meta=dict(codegen_result.meta or {}),
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
    asset_pack: dict[str, Any],
    asset_bank_files: list[dict[str, str]],
    runtime_asset_manifest: dict[str, Any],
    memory_hint: str = "",
    memory_tokens: list[str] | None = None,
    request_capability_hint: str = "",
    generated_genre_directive: str = "",
) -> ProductionBuildResult:
    core_loop_type = _normalize_core_loop_type(core_loop_type)
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
        asset_pack=asset_pack,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
        memory_hint=memory_hint,
        memory_tokens=memory_tokens,
        request_capability_hint=request_capability_hint,
        generated_genre_directive=generated_genre_directive,
    )
