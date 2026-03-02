from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.builder_parts.bundle import _extract_hybrid_bundle_from_inline_html
from app.orchestration.nodes.builder_parts.html_runtime import _build_hybrid_engine_html
from app.orchestration.nodes.builder_parts.html_runtime_config import MODE_CONFIG_BY_LOOP
from app.orchestration.nodes.builder_parts.mode import _candidate_composite_score, _candidate_variation_hints
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import BuildArtifactPayload, DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus
from app.services.quality_types import GameplayGateResult, QualityGateResult, SmokeCheckResult


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
    smoke: SmokeCheckResult
    visual: QualityGateResult
    builder_score: float
    placeholder_heavy: bool
    placeholder_score: float
    runtime_warning_penalty: float
    runtime_warning_codes: list[str]


def _coerce_float(value: object, *, fallback: float) -> float:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return float(text)
        except Exception:
            return fallback
    return fallback


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
    }
    score = 0.0
    for token in warnings:
        code = str(token).strip().casefold()
        score += penalties.get(code, 0.0)
    return round(min(28.0, score), 2)


def _runtime_structure_signature(*, html_content: str) -> str:
    lowered = html_content.casefold()
    script_start = lowered.find("<script>")
    script_end = lowered.rfind("</script>")
    if script_start >= 0 and script_end > script_start:
        lowered = lowered[script_start + len("<script>"):script_end]
    lowered = re.sub(r"\"[^\"]*\"|'[^']*'", "\"s\"", lowered)
    lowered = re.sub(r"\b\d+(?:\.\d+)?\b", "0", lowered)
    lowered = re.sub(r"\s+", "", lowered)
    digest = hashlib.sha256(lowered.encode("utf-8")).hexdigest()
    return digest[:24]


def _build_builder_refinement_hint(
    *,
    keyword: str,
    core_loop_type: str,
    quality: QualityGateResult,
    gameplay: GameplayGateResult,
    visual: QualityGateResult,
    smoke: SmokeCheckResult,
) -> str:
    parts: list[str] = [
        "Strengthen gameplay depth and visual readability for this build.",
        "Avoid primitive rectangle-only silhouettes; use layered sprites, distinct character proportions, and impact effects.",
        "Keep the runtime full-screen in embedded iframe with stable 16:9 stage composition and no clipped canvas.",
        f"Honor requested intent from keyword: {keyword}.",
        f"Core loop must remain consistent with mode {core_loop_type}.",
    ]
    if quality.failed_checks:
        parts.append(f"Quality gaps: {', '.join(quality.failed_checks[:6])}.")
    if gameplay.failed_checks:
        parts.append(f"Gameplay gaps: {', '.join(gameplay.failed_checks[:6])}.")
    if visual.failed_checks:
        parts.append(f"Visual gaps: {', '.join(visual.failed_checks[:6])}.")
    if smoke.reason:
        parts.append(f"Runtime smoke note: {smoke.reason}.")
    return " ".join(parts)


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
    quality = deps.quality_service.evaluate_quality_contract(html_content, design_spec=design_spec)
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
        smoke=smoke,
        visual=visual,
        builder_score=score,
        placeholder_heavy=placeholder_heavy,
        placeholder_score=placeholder_score,
        runtime_warning_penalty=runtime_warning_penalty,
        runtime_warning_codes=runtime_warning_codes,
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _build_rebuild_feedback_hint(state: PipelineState) -> tuple[str, list[str]]:
    feedback = state["outputs"].get("qa_rebuild_feedback")
    if not isinstance(feedback, dict):
        return "", []

    gate = str(feedback.get("gate", "")).strip().casefold()
    reason = str(feedback.get("reason", "")).strip()
    failed_checks = _string_list(feedback.get("failed_checks"))
    fatal_errors = _string_list(feedback.get("fatal_errors"))
    warning_rows = _string_list(feedback.get("non_fatal_warnings"))
    tokens = failed_checks + fatal_errors
    token_preview = ", ".join(tokens[:6]) if tokens else ""

    if gate == "runtime":
        hint = (
            "Prior QA runtime failure detected. Ensure iframe-ready auto-start without click dependency, "
            "stable first 3 seconds, and no immediate game-over overlay."
        )
        if token_preview:
            hint += f" Runtime issues: {token_preview}."
        if reason:
            hint += f" Reason: {reason}."
        if warning_rows:
            hint += f" Warnings: {', '.join(warning_rows[:4])}."
        return hint, tokens

    if gate == "quality":
        hint = "Prior QA quality gate failed. Reinforce viewport/readability/contract tokens and runtime shell compatibility."
        if token_preview:
            hint += f" Failed checks: {token_preview}."
        if reason:
            hint += f" Reason: {reason}."
        return hint, tokens

    if gate == "gameplay":
        hint = "Prior QA gameplay gate failed. Strengthen core loop pressure, restart loop, telegraphs, and risk-reward pacing."
        if token_preview:
            hint += f" Failed checks: {token_preview}."
        if reason:
            hint += f" Reason: {reason}."
        return hint, tokens

    if gate == "artifact":
        hint = "Prior artifact contract gate failed. Increase procedural layer richness, animation hooks, and asset pipeline metadata integrity."
        if token_preview:
            hint += f" Failed checks: {token_preview}."
        if reason:
            hint += f" Reason: {reason}."
        return hint, tokens

    if gate == "visual":
        hint = "Prior visual gate retry request detected. Improve contrast, color diversity, silhouette clarity, and motion readability."
        if token_preview:
            hint += f" Failed checks: {token_preview}."
        if reason:
            hint += f" Reason: {reason}."
        return hint, tokens

    if not reason and not token_preview:
        return "", []
    generic = "Prior QA feedback exists. Resolve recent gate failures before adding new complexity."
    if token_preview:
        generic += f" Issues: {token_preview}."
    if reason:
        generic += f" Reason: {reason}."
    return generic, tokens


def _resolve_codegen_pass_budget(
    *,
    configured_passes: int,
    has_feedback_hint: bool,
    build_iteration: int,
) -> int:
    base_passes = max(0, int(configured_passes))
    if has_feedback_hint or build_iteration > 1:
        return max(base_passes, 2)
    return base_passes


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
    configured_candidate_count = max(1, int(deps.vertex_service.settings.builder_candidate_count))
    candidate_count = 1
    variation_hints = _candidate_variation_hints(core_loop_type=core_loop_type, candidate_count=candidate_count)
    design_spec_dump = design_spec.model_dump()
    rebuild_feedback_hint, rebuild_feedback_tokens = _build_rebuild_feedback_hint(state)
    qa_visual_feedback = state["outputs"].get("qa_visual_feedback")
    visual_feedback_hint = ""
    visual_feedback_failed_checks: list[str] = []
    if isinstance(qa_visual_feedback, dict):
        failed_checks = qa_visual_feedback.get("failed_checks")
        if isinstance(failed_checks, list):
            visual_feedback_failed_checks = [str(item).strip() for item in failed_checks if str(item).strip()]
        if visual_feedback_failed_checks:
            visual_feedback_hint = (
                "Prior QA visual issues: "
                + ", ".join(visual_feedback_failed_checks[:6])
                + ". Improve contrast, color diversity, edge definition, and readable motion cues."
            )

    normalized_memory_hint = memory_hint.strip()
    normalized_request_capability_hint = request_capability_hint.strip()
    normalized_generated_genre_directive = generated_genre_directive.strip()
    memory_feedback_tokens = [str(item).strip() for item in (memory_tokens or []) if str(item).strip()]

    combined_feedback_hint = " ".join(
        chunk
        for chunk in (
            rebuild_feedback_hint,
            visual_feedback_hint,
            normalized_request_capability_hint,
            normalized_generated_genre_directive,
            normalized_memory_hint,
        )
        if chunk
    ).strip()
    previous_artifact_html = str(state["outputs"].get("artifact_html", "")).strip()
    reuse_previous_artifact_seed = bool(
        previous_artifact_html
        and combined_feedback_hint
        and int(state.get("build_iteration", 0)) > 1
    )
    configured_codegen_passes = int(deps.vertex_service.settings.builder_codegen_passes)
    codegen_pass_budget = _resolve_codegen_pass_budget(
        configured_passes=configured_codegen_passes,
        has_feedback_hint=bool(combined_feedback_hint),
        build_iteration=int(state.get("build_iteration", 0)),
    )

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.DEVELOPER,
        message=f"Production V2 generation started (iteration={state['build_iteration']}).",
        metadata={
            "iteration": state["build_iteration"],
            "core_loop_type": core_loop_type,
            "asset_pack": asset_pack["name"],
            "configured_candidate_count": configured_candidate_count,
            "candidate_count": candidate_count,
            "rebuild_feedback_hint_applied": bool(rebuild_feedback_hint),
            "rebuild_feedback_tokens": rebuild_feedback_tokens,
            "visual_feedback_hint_applied": bool(visual_feedback_hint),
            "visual_feedback_failed_checks": visual_feedback_failed_checks,
            "memory_hint_applied": bool(normalized_memory_hint),
            "request_capability_hint_applied": bool(normalized_request_capability_hint),
            "generated_genre_directive_applied": bool(normalized_generated_genre_directive),
            "memory_feedback_tokens": memory_feedback_tokens,
            "reuse_previous_artifact_seed": reuse_previous_artifact_seed,
            "configured_codegen_passes": configured_codegen_passes,
            "effective_codegen_pass_budget": codegen_pass_budget,
        },
    )

    candidate_rows: list[dict[str, Any]] = []
    for index, variation_hint in enumerate(variation_hints, start=1):
        effective_variation_hint = (
            f"{variation_hint} | {combined_feedback_hint}"
            if combined_feedback_hint
            else variation_hint
        )
        generated_config = deps.vertex_service.generate_game_config(
            keyword=state["keyword"],
            title=title,
            genre=genre,
            objective=gdd.objective,
            design_spec=design_spec_dump,
            variation_hint=effective_variation_hint,
        )
        base_candidate_html = _build_hybrid_engine_html(
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
            game_config=generated_config.payload,
            asset_pack=asset_pack,
            asset_manifest=runtime_asset_manifest,
        )
        candidate_html = previous_artifact_html if reuse_previous_artifact_seed else base_candidate_html
        codegen_meta_rows: list[dict[str, Any]] = []
        if reuse_previous_artifact_seed:
            codegen_meta_rows.append(
                {
                    "pass": 0,
                    "generation_source": "previous_artifact_seed",
                    "model": None,
                    "reason": "feedback_refinement_seed",
                }
            )
        for pass_index in range(codegen_pass_budget):
            codegen_result = deps.vertex_service.generate_codegen_candidate_artifact(
                keyword=state["keyword"],
                title=title,
                genre=genre,
                objective=gdd.objective,
                core_loop_type=core_loop_type,
                variation_hint=effective_variation_hint,
                design_spec=design_spec_dump,
                asset_pack=asset_pack,
                html_content=candidate_html,
            )
            generated_candidate_html = str(codegen_result.payload.get("artifact_html", "")).strip()
            if generated_candidate_html:
                candidate_html = generated_candidate_html
            codegen_meta_rows.append(
                {
                    "pass": pass_index + 1,
                    "generation_source": codegen_result.meta.get("generation_source", "stub"),
                    "model": codegen_result.meta.get("model"),
                    "reason": codegen_result.meta.get("reason"),
                }
            )
        base_assessment = _assess_artifact_quality(
            deps=deps,
            html_content=base_candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            core_loop_type=core_loop_type,
            keyword=state["keyword"],
            artifact_files=asset_bank_files,
            slug=slug,
        )
        base_composite_score = _candidate_composite_score(
            quality_score=base_assessment.quality.score,
            gameplay_score=base_assessment.gameplay.score,
            quality_ok=base_assessment.quality.ok,
            gameplay_ok=base_assessment.gameplay.ok,
        )
        candidate_assessment = _assess_artifact_quality(
            deps=deps,
            html_content=candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            core_loop_type=core_loop_type,
            keyword=state["keyword"],
            artifact_files=asset_bank_files,
            slug=slug,
        )
        composite_score = _candidate_composite_score(
            quality_score=candidate_assessment.quality.score,
            gameplay_score=candidate_assessment.gameplay.score,
            quality_ok=candidate_assessment.quality.ok,
            gameplay_ok=candidate_assessment.gameplay.ok,
        )
        codegen_regressed = (
            base_composite_score > composite_score
            or (base_assessment.builder_score - candidate_assessment.builder_score) >= 1.0
            or (bool(candidate_assessment.runtime_warning_codes) and not bool(base_assessment.runtime_warning_codes))
        )
        if codegen_regressed:
            candidate_html = base_candidate_html
            candidate_assessment = base_assessment
            composite_score = base_composite_score
            codegen_meta_rows.append(
                {
                    "pass": 0,
                    "generation_source": "template_baseline",
                    "model": None,
                    "reason": "codegen_regression_guard",
                    "baseline_composite_score": base_composite_score,
                    "baseline_builder_score": base_assessment.builder_score,
                }
            )

        candidate_row = {
            "index": index,
            "variation_hint": variation_hint,
            "effective_variation_hint": effective_variation_hint,
            "artifact_html": candidate_html,
            "baseline_artifact_html": base_candidate_html,
            "generation_meta": generated_config.meta,
            "quality_ok": candidate_assessment.quality.ok,
            "quality_score": candidate_assessment.quality.score,
            "gameplay_ok": candidate_assessment.gameplay.ok,
            "gameplay_score": candidate_assessment.gameplay.score,
            "visual_ok": candidate_assessment.visual.ok,
            "visual_score": candidate_assessment.visual.score,
            "smoke_ok": candidate_assessment.smoke.ok,
            "smoke_reason": candidate_assessment.smoke.reason,
            "builder_quality_score": candidate_assessment.builder_score,
            "placeholder_heavy": candidate_assessment.placeholder_heavy,
            "placeholder_score": candidate_assessment.placeholder_score,
            "runtime_warning_penalty": candidate_assessment.runtime_warning_penalty,
            "runtime_warning_codes": candidate_assessment.runtime_warning_codes,
            "composite_score": composite_score,
            "asset_pack": asset_pack["name"],
            "codegen_passes": codegen_meta_rows,
        }
        candidate_rows.append(candidate_row)

        append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            agent_name=PipelineAgentName.DEVELOPER,
            message=f"Candidate {index}/{candidate_count} evaluated.",
            metadata={
                "iteration": state["build_iteration"],
                "candidate_index": index,
                "quality_score": candidate_assessment.quality.score,
                "gameplay_score": candidate_assessment.gameplay.score,
                "visual_score": candidate_assessment.visual.score,
                "smoke_ok": candidate_assessment.smoke.ok,
                "builder_quality_score": candidate_assessment.builder_score,
                "placeholder_heavy": candidate_assessment.placeholder_heavy,
                "placeholder_score": candidate_assessment.placeholder_score,
                "runtime_warning_penalty": candidate_assessment.runtime_warning_penalty,
                "runtime_warning_codes": candidate_assessment.runtime_warning_codes,
                "composite_score": composite_score,
                "generation_source": generated_config.meta.get("generation_source", "stub"),
                "model": generated_config.meta.get("model"),
                "asset_pack": asset_pack["name"],
                "codegen_passes": codegen_meta_rows,
                "effective_variation_hint": effective_variation_hint,
            },
        )

    best_candidate = max(
        candidate_rows,
        key=lambda row: (
            float(row.get("builder_quality_score", 0.0)),
            float(row["composite_score"]),
            int(row["gameplay_score"]),
            int(row["quality_score"]),
        ),
    )
    selected_generation_meta = dict(best_candidate.get("generation_meta", {}))
    selected_html = str(best_candidate["artifact_html"])
    selected_baseline_html = str(best_candidate.get("baseline_artifact_html", selected_html))

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.DEVELOPER,
        message="Final polish pass started for selected candidate.",
        metadata={
            "iteration": state["build_iteration"],
            "selected_candidate": best_candidate["index"],
            "selected_composite_score": best_candidate["composite_score"],
        },
    )

    selected_assessment = _assess_artifact_quality(
        deps=deps,
        html_content=selected_html,
        design_spec=design_spec_dump,
        genre=genre,
        core_loop_type=core_loop_type,
        keyword=state["keyword"],
        artifact_files=asset_bank_files,
        slug=slug,
    )
    baseline_assessment = _assess_artifact_quality(
        deps=deps,
        html_content=selected_baseline_html,
        design_spec=design_spec_dump,
        genre=genre,
        core_loop_type=core_loop_type,
        keyword=state["keyword"],
        artifact_files=asset_bank_files,
        slug=slug,
    )

    polish_result = deps.vertex_service.polish_hybrid_artifact(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        html_content=selected_html,
    )
    polished_html = str(polish_result.payload.get("artifact_html", "")).strip() or selected_html
    polished_assessment = _assess_artifact_quality(
        deps=deps,
        html_content=polished_html,
        design_spec=design_spec_dump,
        genre=genre,
        core_loop_type=core_loop_type,
        keyword=state["keyword"],
        artifact_files=asset_bank_files,
        slug=slug,
    )
    runtime_guard_candidates: list[tuple[str, _ArtifactAssessment]] = [
        ("polished", polished_assessment),
        ("selected", selected_assessment),
        ("baseline", baseline_assessment),
    ]
    runtime_guard_result: dict[str, Any] = {"chosen": None, "reason": None, "probes": [], "refinement": []}
    preferred_label: str | None = None
    preferred_assessment: _ArtifactAssessment | None = None
    for label, assessment in runtime_guard_candidates:
        runtime_guard_result["probes"].append(
            {
                "label": label,
                "ok": bool(assessment.smoke.ok),
                "reason": assessment.smoke.reason,
                "console_errors": assessment.smoke.console_errors or [],
                "fatal_errors": assessment.smoke.fatal_errors or [],
                "non_fatal_warnings": assessment.smoke.non_fatal_warnings or [],
                "quality_score": assessment.quality.score,
                "gameplay_score": assessment.gameplay.score,
                "visual_score": assessment.visual.score,
                "builder_quality_score": assessment.builder_score,
                "placeholder_heavy": assessment.placeholder_heavy,
                "placeholder_score": assessment.placeholder_score,
                "runtime_warning_penalty": assessment.runtime_warning_penalty,
                "runtime_warning_codes": assessment.runtime_warning_codes,
            }
        )
        if assessment.smoke.ok and (
            preferred_assessment is None or assessment.builder_score > preferred_assessment.builder_score
        ):
            preferred_label = label
            preferred_assessment = assessment

    if preferred_assessment is None:
        preferred_label = "baseline_force"
        preferred_assessment = baseline_assessment
        runtime_guard_result["reason"] = "builder_runtime_guard_all_failed"
    else:
        runtime_guard_result["reason"] = preferred_assessment.smoke.reason
    runtime_guard_result["chosen"] = preferred_label

    refinement_round_limit = _coerce_int(
        getattr(deps.vertex_service.settings, "builder_refinement_rounds", 1),
        fallback=1,
    )
    refinement_round_limit = max(0, min(refinement_round_limit, 3))
    refinement_target_score = _coerce_float(
        getattr(deps.vertex_service.settings, "builder_refinement_target_score", 78.0),
        fallback=78.0,
    )
    refinement_target_score = max(0.0, min(refinement_target_score, 100.0))
    refinement_rounds_executed = 0

    if preferred_assessment.smoke.ok and preferred_assessment.builder_score < refinement_target_score:
        for round_index in range(1, refinement_round_limit + 1):
            refinement_rounds_executed += 1
            refinement_hint = _build_builder_refinement_hint(
                keyword=state["keyword"],
                core_loop_type=core_loop_type,
                quality=preferred_assessment.quality,
                gameplay=preferred_assessment.gameplay,
                visual=preferred_assessment.visual,
                smoke=preferred_assessment.smoke,
            )
            refinement_result = deps.vertex_service.generate_codegen_candidate_artifact(
                keyword=state["keyword"],
                title=title,
                genre=genre,
                objective=gdd.objective,
                core_loop_type=core_loop_type,
                variation_hint=refinement_hint,
                design_spec=design_spec_dump,
                asset_pack=asset_pack,
                html_content=preferred_assessment.html,
            )
            refined_html = str(refinement_result.payload.get("artifact_html", "")).strip() or preferred_assessment.html
            refined_assessment = _assess_artifact_quality(
                deps=deps,
                html_content=refined_html,
                design_spec=design_spec_dump,
                genre=genre,
                core_loop_type=core_loop_type,
                keyword=state["keyword"],
                artifact_files=asset_bank_files,
                slug=slug,
            )
            promoted = refined_assessment.smoke.ok and refined_assessment.builder_score > preferred_assessment.builder_score
            runtime_guard_result["refinement"].append(
                {
                    "round": round_index,
                    "promoted": promoted,
                    "quality_score": refined_assessment.quality.score,
                    "gameplay_score": refined_assessment.gameplay.score,
                    "visual_score": refined_assessment.visual.score,
                    "builder_quality_score": refined_assessment.builder_score,
                    "placeholder_heavy": refined_assessment.placeholder_heavy,
                    "placeholder_score": refined_assessment.placeholder_score,
                    "runtime_warning_penalty": refined_assessment.runtime_warning_penalty,
                    "runtime_warning_codes": refined_assessment.runtime_warning_codes,
                    "smoke_ok": refined_assessment.smoke.ok,
                    "smoke_reason": refined_assessment.smoke.reason,
                    "generation_source": refinement_result.meta.get("generation_source", "stub"),
                    "model": refinement_result.meta.get("model"),
                    "reason": refinement_result.meta.get("reason"),
                }
            )
            if promoted:
                preferred_assessment = refined_assessment
                preferred_label = f"refined_{round_index}"
                runtime_guard_result["chosen"] = preferred_label
                runtime_guard_result["reason"] = refined_assessment.smoke.reason
                if preferred_assessment.builder_score >= refinement_target_score:
                    break

    artifact_html = preferred_assessment.html
    final_quality_score = preferred_assessment.quality.score
    final_gameplay_score = preferred_assessment.gameplay.score
    final_visual_score = preferred_assessment.visual.score
    final_builder_quality_score = preferred_assessment.builder_score
    final_placeholder_heavy = preferred_assessment.placeholder_heavy
    final_placeholder_score = preferred_assessment.placeholder_score
    final_runtime_warning_penalty = preferred_assessment.runtime_warning_penalty
    final_runtime_warning_codes = list(preferred_assessment.runtime_warning_codes)
    final_composite_score = _candidate_composite_score(
        quality_score=final_quality_score,
        gameplay_score=final_gameplay_score,
        quality_ok=preferred_assessment.quality.ok,
        gameplay_ok=preferred_assessment.gameplay.ok,
    )
    selected_composite = float(best_candidate["composite_score"])
    use_polished = preferred_label == "polished"

    builder_strategy = "production_v3_candidates_codegen_qa_polish"
    candidate_scoreboard = [
        {
            "index": int(row["index"]),
            "quality_score": int(row["quality_score"]),
            "gameplay_score": int(row["gameplay_score"]),
            "visual_score": int(row.get("visual_score", 0)),
            "smoke_ok": bool(row.get("smoke_ok")),
            "smoke_reason": row.get("smoke_reason"),
            "builder_quality_score": float(row.get("builder_quality_score", 0.0)),
            "placeholder_heavy": bool(row.get("placeholder_heavy", False)),
            "placeholder_score": float(row.get("placeholder_score", 0.0)),
            "runtime_warning_penalty": float(row.get("runtime_warning_penalty", 0.0)),
            "runtime_warning_codes": [str(item) for item in row.get("runtime_warning_codes", []) if str(item).strip()],
            "composite_score": float(row["composite_score"]),
            "quality_ok": bool(row["quality_ok"]),
            "gameplay_ok": bool(row["gameplay_ok"]),
            "generation_source": row["generation_meta"].get("generation_source", "stub"),
            "model": row["generation_meta"].get("model"),
            "asset_pack": row.get("asset_pack"),
            "codegen_passes": row.get("codegen_passes", []),
        }
        for row in candidate_rows
    ]

    quality_floor_score = _coerce_int(
        getattr(deps.vertex_service.settings, "builder_quality_floor_score", 72),
        fallback=72,
    )
    quality_floor_score = max(0, min(100, quality_floor_score))
    quality_floor_enforced = bool(
        getattr(deps.vertex_service.settings, "builder_quality_floor_enforced", True)
    )
    quality_floor_fail_reasons: list[str] = []
    if not preferred_assessment.smoke.ok:
        quality_floor_fail_reasons.append("runtime_smoke_failed")
    if final_builder_quality_score < float(quality_floor_score):
        quality_floor_fail_reasons.append("builder_quality_floor_unmet")
    if final_placeholder_heavy:
        quality_floor_fail_reasons.append("placeholder_visual_detected")
    if final_runtime_warning_codes:
        quality_floor_fail_reasons.append("runtime_liveness_warnings_detected")

    runtime_structure_signature = _runtime_structure_signature(html_content=artifact_html)
    runtime_signature_guard_enabled = bool(
        getattr(deps.vertex_service.settings, "builder_runtime_signature_guard", True)
    )
    duplicate_runtime_signature = False
    repository = getattr(deps, "repository", None)
    list_registry = getattr(repository, "list_asset_registry", None)
    if runtime_signature_guard_enabled and callable(list_registry):
        try:
            recent_rows: list[dict[str, Any]] = []
            for loop_key in MODE_CONFIG_BY_LOOP.keys():
                rows = list_registry(core_loop_type=str(loop_key), limit=12)
                if isinstance(rows, list):
                    recent_rows.extend([row for row in rows if isinstance(row, dict)])
        except Exception:
            recent_rows = []
        for row in recent_rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("game_slug", "")).strip() == slug:
                continue
            metadata = row.get("metadata")
            if not isinstance(metadata, dict):
                continue
            signature = str(metadata.get("runtime_structure_signature", "")).strip()
            if signature and signature == runtime_structure_signature:
                duplicate_runtime_signature = True
                break
    if duplicate_runtime_signature:
        quality_floor_fail_reasons.append("runtime_structure_duplicate")

    quality_floor_passed = len(quality_floor_fail_reasons) == 0

    artifact_files: list[dict[str, str]] | None = None
    artifact_manifest: dict[str, object] | None = None

    hybrid_bundle = _extract_hybrid_bundle_from_inline_html(
        slug=slug,
        inline_html=artifact_html,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
    )
    if not hybrid_bundle:
        fallback_files = [
            {
                "path": f"games/{slug}/index.html",
                "content": artifact_html,
                "content_type": "text/html; charset=utf-8",
            },
            *asset_bank_files,
        ]
        fallback_asset_manifest = runtime_asset_manifest if isinstance(runtime_asset_manifest, dict) else {}
        fallback_manifest = {
            "schema_version": 1,
            "entrypoint": f"games/{slug}/index.html",
            "files": [row["path"] for row in fallback_files],
            "bundle_kind": "hybrid_engine",
            "modules": [
                "runtime_bootstrap",
                "input_controls",
                "spawn_system",
                "combat_or_navigation_loop",
                "render_pipeline",
                "hud_overlay",
                "audio_feedback",
            ],
            "runtime_hooks": [
                "requestAnimationFrame",
                "pickWeighted",
                "applyRelicSynergy",
                "spawnMiniBoss",
                "drawPostFx",
                "update",
                "draw",
                "playSfx",
            ],
            "asset_manifest": fallback_asset_manifest,
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
        artifact_html=artifact_html,
        entrypoint_path=f"games/{slug}/index.html",
        artifact_files=artifact_files,
        artifact_manifest=artifact_manifest,
    )

    metadata = {
        "builder_strategy": builder_strategy,
        "genre_engine_selected": core_loop_type,
        "asset_pack": asset_pack["name"],
        "asset_pipeline_selected_variant": (
            runtime_asset_manifest.get("asset_pipeline", {}).get("selected_variant")
            if isinstance(runtime_asset_manifest.get("asset_pipeline"), dict)
            else None
        ),
        "asset_pipeline_selected_theme": (
            runtime_asset_manifest.get("asset_pipeline", {}).get("selected_theme")
            if isinstance(runtime_asset_manifest.get("asset_pipeline"), dict)
            else None
        ),
        "artifact_file_count": len(build_artifact.artifact_files or []),
        "configured_candidate_count": configured_candidate_count,
        "candidate_count": candidate_count,
        "codegen_enabled": bool(deps.vertex_service.settings.builder_codegen_enabled),
        "codegen_passes_per_candidate": configured_codegen_passes,
        "effective_codegen_passes_per_candidate": codegen_pass_budget,
        "reuse_previous_artifact_seed": reuse_previous_artifact_seed,
        "selected_candidate_index": int(best_candidate["index"]),
        "selected_candidate_score": selected_composite,
        "final_quality_score": final_quality_score,
        "final_gameplay_score": final_gameplay_score,
        "final_visual_score": final_visual_score,
        "final_builder_quality_score": final_builder_quality_score,
        "final_placeholder_heavy": final_placeholder_heavy,
        "final_placeholder_score": final_placeholder_score,
        "final_runtime_warning_penalty": final_runtime_warning_penalty,
        "final_runtime_warning_codes": final_runtime_warning_codes,
        "runtime_structure_signature": runtime_structure_signature,
        "duplicate_runtime_signature": duplicate_runtime_signature,
        "runtime_signature_guard_enabled": runtime_signature_guard_enabled,
        "final_smoke_ok": preferred_assessment.smoke.ok,
        "final_smoke_reason": preferred_assessment.smoke.reason,
        "final_composite_score": final_composite_score,
        "quality_floor_score": quality_floor_score,
        "quality_floor_enforced": quality_floor_enforced,
        "quality_floor_passed": quality_floor_passed,
        "quality_floor_fail_reasons": quality_floor_fail_reasons,
        "rebuild_feedback_hint_applied": bool(rebuild_feedback_hint),
        "rebuild_feedback_tokens": rebuild_feedback_tokens,
        "memory_hint_applied": bool(normalized_memory_hint),
        "request_capability_hint_applied": bool(normalized_request_capability_hint),
        "generated_genre_directive_applied": bool(normalized_generated_genre_directive),
        "memory_tokens": memory_feedback_tokens,
        "polish_applied": use_polished,
        "final_variant_label": preferred_label,
        "refinement_target_score": refinement_target_score,
        "refinement_round_limit": refinement_round_limit,
        "refinement_rounds_executed": refinement_rounds_executed,
        "polish_generation_source": polish_result.meta.get("generation_source", "stub"),
        "polish_model": polish_result.meta.get("model"),
        "polish_reason": polish_result.meta.get("reason"),
        "runtime_guard": runtime_guard_result,
        "candidate_scoreboard": candidate_scoreboard,
    }
    return ProductionBuildResult(
        build_artifact=build_artifact,
        selected_generation_meta=selected_generation_meta,
        metadata=metadata,
    )
