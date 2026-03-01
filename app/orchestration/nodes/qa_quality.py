from __future__ import annotations

from collections.abc import Iterable

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus

CRITICAL_QUALITY_FAILURE_CODES = {
    "trivial_score_button_template",
    "click_only_interaction",
}
CRITICAL_GAMEPLAY_FAILURE_CODES = {
    "missing_realtime_loop",
    "no_enemy_pressure",
    "flat_scoring_loop",
    "genre_engine_mismatch",
    "keyword_engine_mismatch_flight",
    "flight_mechanics_not_found",
    "f1_mechanics_not_found",
    "f1_quantized_steering",
    "quantized_lane_steering",
}
CRITICAL_VISUAL_FAILURE_CODES = {
    "visual_metrics_missing",
    "visual_palette_too_flat",
    "visual_shape_definition_too_low",
}
CRITICAL_ARTIFACT_FAILURE_CODES = {
    "insufficient_image_assets",
    "insufficient_animation_hooks",
    "insufficient_procedural_layers",
    "unsupported_bundle_kind",
    "asset_policy_mode_mismatch",
    "external_image_generation_not_disabled",
    "asset_pipeline_metadata_missing",
    "asset_pipeline_not_automated",
    "asset_pipeline_variant_count_invalid",
}


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


def _has_critical_failure(failed_checks: list[str], critical_codes: set[str]) -> bool:
    normalized = {str(item).strip().casefold() for item in failed_checks if str(item).strip()}
    return bool(normalized & critical_codes)


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.QA_QUALITY,
        agent_name=PipelineAgentName.QA_QUALITY,
    )
    if gated_state is not None:
        return gated_state

    runtime_snapshot = state["outputs"].get("runtime_smoke_result")
    runtime_row = runtime_snapshot if isinstance(runtime_snapshot, dict) else {}
    visual_metrics = runtime_row.get("visual_metrics") if isinstance(runtime_row.get("visual_metrics"), dict) else {}

    artifact_html = str(state["outputs"].get("artifact_html", ""))
    design_spec = state["outputs"].get("design_spec", {})
    typed_design_spec = design_spec if isinstance(design_spec, dict) else None

    quality_result = deps.quality_service.evaluate_quality_contract(
        artifact_html,
        design_spec=typed_design_spec,
    )
    gameplay_result = deps.quality_service.evaluate_gameplay_gate(
        artifact_html,
        design_spec=typed_design_spec,
        genre=str(state["outputs"].get("game_genre", "")),
        genre_engine=str(state["outputs"].get("genre_engine", "")),
        keyword=str(state.get("keyword", "")),
    )
    visual_result = deps.quality_service.evaluate_visual_gate(
        visual_metrics,
        genre_engine=str(state["outputs"].get("genre_engine", "")),
    )
    artifact_result = deps.quality_service.evaluate_artifact_contract(
        state["outputs"].get("artifact_manifest") if isinstance(state["outputs"].get("artifact_manifest"), dict) else None,
        art_direction_contract=state["outputs"].get("art_direction_contract")
        if isinstance(state["outputs"].get("art_direction_contract"), dict)
        else None,
    )

    existing_rows = state["outputs"].get("qa_improvement_items")
    improvement_items: list[dict[str, object]] = (
        [dict(item) for item in existing_rows if isinstance(item, dict)] if isinstance(existing_rows, list) else []
    )
    quality_failed_checks = [str(item).strip() for item in quality_result.failed_checks if str(item).strip()]
    gameplay_failed_checks = [str(item).strip() for item in gameplay_result.failed_checks if str(item).strip()]
    visual_failed_checks = [str(item).strip() for item in visual_result.failed_checks if str(item).strip()]
    artifact_failed_checks = [str(item).strip() for item in artifact_result.failed_checks if str(item).strip()]

    if not quality_result.ok:
        improvement_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "quality_score_below_threshold",
                "severity": "medium",
                "tokens": quality_failed_checks,
                "metrics": {"score": quality_result.score, "threshold": quality_result.threshold},
            }
        )
    if not gameplay_result.ok:
        improvement_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "gameplay_depth_below_threshold",
                "severity": "high",
                "tokens": gameplay_failed_checks,
                "metrics": {"score": gameplay_result.score, "threshold": gameplay_result.threshold},
            }
        )
    if not visual_result.ok:
        improvement_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "visual_quality_below_threshold",
                "severity": "medium",
                "tokens": visual_failed_checks,
                "metrics": {"score": visual_result.score, "threshold": visual_result.threshold},
            }
        )
    if not artifact_result.ok:
        improvement_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "artifact_contract_below_threshold",
                "severity": "high",
                "tokens": artifact_failed_checks,
                "metrics": {"score": artifact_result.score, "threshold": artifact_result.threshold},
            }
        )

    runtime_warnings = _as_str_list(runtime_row.get("non_fatal_warnings"))
    if runtime_warnings:
        improvement_items.append(
            {
                "stage": PipelineStage.QA_RUNTIME.value,
                "reason": "runtime_warning_detected",
                "severity": "low",
                "tokens": runtime_warnings,
                "metrics": {"warning_count": len(runtime_warnings)},
            }
        )

    state["outputs"]["qa_improvement_items"] = improvement_items
    state["outputs"]["qa_soft_fail"] = len(improvement_items) > 0
    if visual_failed_checks:
        state["outputs"]["qa_visual_feedback"] = {
            "reason": "visual_quality_below_threshold",
            "score": visual_result.score,
            "threshold": visual_result.threshold,
            "failed_checks": visual_failed_checks,
        }
    else:
        state["outputs"].pop("qa_visual_feedback", None)
    state["outputs"]["qa_quality_snapshot"] = {
        "quality_score": quality_result.score,
        "quality_threshold": quality_result.threshold,
        "quality_checks": quality_result.checks,
        "gameplay_score": gameplay_result.score,
        "gameplay_threshold": gameplay_result.threshold,
        "gameplay_checks": gameplay_result.checks,
        "visual_score": visual_result.score,
        "visual_threshold": visual_result.threshold,
        "visual_checks": visual_result.checks,
        "artifact_score": artifact_result.score,
        "artifact_threshold": artifact_result.threshold,
        "artifact_checks": artifact_result.checks,
        "visual_metrics": visual_metrics,
    }

    hard_gate_enabled = bool(getattr(getattr(deps.quality_service, "settings", None), "qa_hard_gate", False))
    critical_quality_failure = (
        (not quality_result.ok and _has_critical_failure(quality_failed_checks, CRITICAL_QUALITY_FAILURE_CODES))
        or (not gameplay_result.ok and _has_critical_failure(gameplay_failed_checks, CRITICAL_GAMEPLAY_FAILURE_CODES))
        or (not visual_result.ok and _has_critical_failure(visual_failed_checks, CRITICAL_VISUAL_FAILURE_CODES))
        or (not artifact_result.ok and _has_critical_failure(artifact_failed_checks, CRITICAL_ARTIFACT_FAILURE_CODES))
    )
    critical_feedback_gate = ""
    critical_feedback_reason = ""
    critical_feedback_checks: list[str] = []
    if not gameplay_result.ok and _has_critical_failure(gameplay_failed_checks, CRITICAL_GAMEPLAY_FAILURE_CODES):
        critical_feedback_gate = "gameplay"
        critical_feedback_reason = "gameplay_depth_below_threshold"
        critical_feedback_checks = gameplay_failed_checks
    elif not visual_result.ok and _has_critical_failure(visual_failed_checks, CRITICAL_VISUAL_FAILURE_CODES):
        critical_feedback_gate = "visual"
        critical_feedback_reason = "visual_quality_below_threshold"
        critical_feedback_checks = visual_failed_checks
    elif not artifact_result.ok and _has_critical_failure(artifact_failed_checks, CRITICAL_ARTIFACT_FAILURE_CODES):
        critical_feedback_gate = "artifact"
        critical_feedback_reason = "artifact_contract_below_threshold"
        critical_feedback_checks = artifact_failed_checks
    elif not quality_result.ok and _has_critical_failure(quality_failed_checks, CRITICAL_QUALITY_FAILURE_CODES):
        critical_feedback_gate = "quality"
        critical_feedback_reason = "quality_score_below_threshold"
        critical_feedback_checks = quality_failed_checks

    state["needs_rebuild"] = False
    summary_message = "Quality QA passed."
    if improvement_items:
        summary_message = f"Quality QA soft-fail: {len(improvement_items)} improvement task(s) queued."

    if hard_gate_enabled and improvement_items:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "qa_hard_gate_blocked"
        return append_log(
            state,
            stage=PipelineStage.QA_QUALITY,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.QA_QUALITY,
            message="Quality QA hard-gate blocked release.",
            reason=state["reason"],
            metadata={
                "quality_score": quality_result.score,
                "quality_threshold": quality_result.threshold,
                "gameplay_score": gameplay_result.score,
                "gameplay_threshold": gameplay_result.threshold,
                "visual_score": visual_result.score,
                "visual_threshold": visual_result.threshold,
                "artifact_score": artifact_result.score,
                "artifact_threshold": artifact_result.threshold,
                "failed_checks": [row["reason"] for row in improvement_items],
                "improvement_count": len(improvement_items),
                "soft_fail": False,
                "hard_gate": True,
                "quality_checks": quality_result.checks,
                "gameplay_checks": gameplay_result.checks,
                "visual_checks": visual_result.checks,
                "artifact_checks": artifact_result.checks,
                "visual_metrics": visual_metrics,
                "non_fatal_warnings": runtime_warnings,
            },
        )

    if critical_quality_failure:
        state["needs_rebuild"] = True
        state["outputs"]["qa_rebuild_feedback"] = {
            "gate": critical_feedback_gate or "quality",
            "reason": critical_feedback_reason or "quality_retry_required",
            "failed_checks": critical_feedback_checks,
            "fatal_errors": [],
            "non_fatal_warnings": runtime_warnings,
        }
        return append_log(
            state,
            stage=PipelineStage.QA_QUALITY,
            status=PipelineStatus.RETRY,
            agent_name=PipelineAgentName.QA_QUALITY,
            message="Quality QA hard-fail: critical deficits detected, rebuilding candidate.",
            reason="retry_builder",
            metadata={
                "quality_score": quality_result.score,
                "quality_threshold": quality_result.threshold,
                "gameplay_score": gameplay_result.score,
                "gameplay_threshold": gameplay_result.threshold,
                "visual_score": visual_result.score,
                "visual_threshold": visual_result.threshold,
                "artifact_score": artifact_result.score,
                "artifact_threshold": artifact_result.threshold,
                "failed_checks": [row["reason"] for row in improvement_items],
                "improvement_count": len(improvement_items),
                "soft_fail": False,
                "critical_quality_failure": True,
                "quality_checks": quality_result.checks,
                "gameplay_checks": gameplay_result.checks,
                "visual_checks": visual_result.checks,
                "artifact_checks": artifact_result.checks,
                "visual_metrics": visual_metrics,
                "non_fatal_warnings": runtime_warnings,
            },
        )

    state["outputs"].pop("qa_rebuild_feedback", None)
    return append_log(
        state,
        stage=PipelineStage.QA_QUALITY,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.QA_QUALITY,
        message=summary_message,
        reason="soft_fail" if improvement_items else None,
        metadata={
            "quality_score": quality_result.score,
            "quality_threshold": quality_result.threshold,
            "gameplay_score": gameplay_result.score,
            "gameplay_threshold": gameplay_result.threshold,
            "visual_score": visual_result.score,
            "visual_threshold": visual_result.threshold,
            "artifact_score": artifact_result.score,
            "artifact_threshold": artifact_result.threshold,
            "failed_checks": [row["reason"] for row in improvement_items],
            "improvement_count": len(improvement_items),
            "soft_fail": bool(improvement_items),
            "quality_checks": quality_result.checks,
            "gameplay_checks": gameplay_result.checks,
            "visual_checks": visual_result.checks,
            "artifact_checks": artifact_result.checks,
            "visual_metrics": visual_metrics,
            "non_fatal_warnings": runtime_warnings,
        },
    )
