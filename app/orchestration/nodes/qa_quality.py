from __future__ import annotations

from collections.abc import Iterable

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus

def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


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

    state["needs_rebuild"] = False
    summary_message = "Quality QA passed."
    if improvement_items:
        summary_message = f"Quality QA soft-fail: {len(improvement_items)} improvement task(s) queued."

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
            "deliverables": ["quality_scorecard", "qa_improvement_queue_items"],
            "contract_status": "warn" if improvement_items else "pass",
            "contract_summary": summary_message,
            "contribution_score": 3.9 if improvement_items else 4.1,
        },
    )
