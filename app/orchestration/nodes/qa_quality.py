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
    intent_contract = state["outputs"].get("intent_contract")
    typed_intent_contract = intent_contract if isinstance(intent_contract, dict) else None
    synapse_contract = state["outputs"].get("synapse_contract")
    typed_synapse_contract = synapse_contract if isinstance(synapse_contract, dict) else None

    evaluate_quality = getattr(deps.quality_service, "evaluate_quality_contract")
    try:
        quality_result = evaluate_quality(
            artifact_html,
            design_spec=typed_design_spec,
            genre=str(state["outputs"].get("game_genre", "")),
            genre_engine=str(state["outputs"].get("genre_engine", "")),
            runtime_engine_mode=str(state["outputs"].get("runtime_engine_mode", "")),
            keyword=str(state.get("keyword", "")),
            intent_contract=typed_intent_contract,
            synapse_contract=typed_synapse_contract,
        )
    except TypeError:
        quality_result = evaluate_quality(
            artifact_html,
            design_spec=typed_design_spec,
        )
    gameplay_result = deps.quality_service.evaluate_gameplay_gate(
        artifact_html,
        design_spec=typed_design_spec,
        genre=str(state["outputs"].get("game_genre", "")),
        genre_engine=str(state["outputs"].get("genre_engine", "")),
        keyword=str(state.get("keyword", "")),
        intent_contract=typed_intent_contract,
        synapse_contract=typed_synapse_contract,
    )
    try:
        visual_result = deps.quality_service.evaluate_visual_gate(
            visual_metrics,
            genre_engine=str(state["outputs"].get("genre_engine", "")),
            runtime_engine_mode=str(state["outputs"].get("runtime_engine_mode", "")),
        )
    except TypeError:
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
    evaluate_intent = getattr(deps.quality_service, "evaluate_intent_gate", None)
    if callable(evaluate_intent):
        intent_gate_report = evaluate_intent(
            artifact_html,
            intent_contract=typed_intent_contract,
        )
    else:
        intent_gate_report = {
            "ok": True,
            "score": 100,
            "threshold": 75,
            "failed_items": [],
            "checks": {"intent_gate_unavailable": True},
        }

    existing_rows = state["outputs"].get("qa_improvement_items")
    improvement_items: list[dict[str, object]] = (
        [dict(item) for item in existing_rows if isinstance(item, dict)] if isinstance(existing_rows, list) else []
    )
    quality_failed_checks = [str(item).strip() for item in quality_result.failed_checks if str(item).strip()]
    gameplay_failed_checks = [str(item).strip() for item in gameplay_result.failed_checks if str(item).strip()]
    visual_failed_checks = [str(item).strip() for item in visual_result.failed_checks if str(item).strip()]
    artifact_failed_checks = [str(item).strip() for item in artifact_result.failed_checks if str(item).strip()]
    intent_failed_items = _as_str_list(intent_gate_report.get("failed_items"))

    blocking_items: list[dict[str, object]] = []
    if not quality_result.ok:
        blocking_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "quality_score_below_threshold",
                "severity": "high",
                "tokens": quality_failed_checks,
                "metrics": {"score": quality_result.score, "threshold": quality_result.threshold},
            }
        )
    if not gameplay_result.ok:
        blocking_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "gameplay_depth_below_threshold",
                "severity": "high",
                "tokens": gameplay_failed_checks,
                "metrics": {"score": gameplay_result.score, "threshold": gameplay_result.threshold},
            }
        )
    if not visual_result.ok:
        blocking_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "visual_quality_below_threshold",
                "severity": "high",
                "tokens": visual_failed_checks,
                "metrics": {"score": visual_result.score, "threshold": visual_result.threshold},
            }
        )
    if not artifact_result.ok:
        blocking_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "artifact_contract_below_threshold",
                "severity": "high",
                "tokens": artifact_failed_checks,
                "metrics": {"score": artifact_result.score, "threshold": artifact_result.threshold},
            }
        )
    if not bool(intent_gate_report.get("ok", False)):
        blocking_items.append(
            {
                "stage": PipelineStage.QA_QUALITY.value,
                "reason": "intent_contract_unmet",
                "severity": "high",
                "tokens": intent_failed_items,
                "metrics": {
                    "score": int(intent_gate_report.get("score", 0) or 0),
                    "threshold": int(intent_gate_report.get("threshold", 75) or 75),
                },
            }
        )
    improvement_items.extend(blocking_items)

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
    state["outputs"]["qa_soft_fail"] = False
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
        "intent_gate_report": intent_gate_report,
        "visual_metrics": visual_metrics,
    }
    state["outputs"]["intent_gate_report"] = intent_gate_report

    state["needs_rebuild"] = False
    summary_message = "Quality QA passed."
    blocking_reasons = [str(row.get("reason", "")).strip() for row in blocking_items if str(row.get("reason", "")).strip()]
    if intent_failed_items:
        blocking_reasons.extend([f"intent:{item}" for item in intent_failed_items])
    blocking_reasons = list(dict.fromkeys([reason for reason in blocking_reasons if reason]))
    if blocking_items:
        summary_message = f"Quality QA blocked release: {len(blocking_items)} gate(s) failed."

    state["outputs"].pop("qa_rebuild_feedback", None)
    if blocking_items:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "qa_quality_gate_failed"
        return append_log(
            state,
            stage=PipelineStage.QA_QUALITY,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.QA_QUALITY,
            message=summary_message,
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
                "failed_checks": blocking_reasons,
                "blocking_reasons": blocking_reasons,
                "improvement_count": len(improvement_items),
                "soft_fail": False,
                "quality_checks": quality_result.checks,
                "gameplay_checks": gameplay_result.checks,
                "visual_checks": visual_result.checks,
                "artifact_checks": artifact_result.checks,
                "intent_gate_report": intent_gate_report,
                "visual_metrics": visual_metrics,
                "non_fatal_warnings": runtime_warnings,
                "deliverables": ["quality_scorecard", "qa_gate_block_report"],
                "contract_status": "fail",
                "contract_summary": summary_message,
                "contribution_score": 1.8,
            },
        )

    return append_log(
        state,
        stage=PipelineStage.QA_QUALITY,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.QA_QUALITY,
        message=summary_message,
        reason=None,
        metadata={
            "quality_score": quality_result.score,
            "quality_threshold": quality_result.threshold,
            "gameplay_score": gameplay_result.score,
            "gameplay_threshold": gameplay_result.threshold,
            "visual_score": visual_result.score,
            "visual_threshold": visual_result.threshold,
            "artifact_score": artifact_result.score,
            "artifact_threshold": artifact_result.threshold,
            "failed_checks": [],
            "blocking_reasons": [],
            "improvement_count": len(improvement_items),
            "soft_fail": False,
            "quality_checks": quality_result.checks,
            "gameplay_checks": gameplay_result.checks,
            "visual_checks": visual_result.checks,
            "artifact_checks": artifact_result.checks,
            "intent_gate_report": intent_gate_report,
            "visual_metrics": visual_metrics,
            "non_fatal_warnings": runtime_warnings,
            "deliverables": ["quality_scorecard"],
            "contract_status": "pass",
            "contract_summary": summary_message,
            "contribution_score": 4.2,
        },
    )
