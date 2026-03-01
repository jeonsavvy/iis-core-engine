from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


CRITICAL_RUNTIME_FAILURE_CODES = {
    "boot_flag_missing",
    "runtime_canvas_too_small",
}


def _is_critical_runtime_failure(*, reason: str | None, fatal_errors: list[str] | None) -> bool:
    fatal_rows = [str(item).strip().casefold() for item in (fatal_errors or []) if str(item).strip()]
    if any(code in fatal_rows for code in CRITICAL_RUNTIME_FAILURE_CODES):
        return True
    normalized_reason = str(reason or "").strip().casefold()
    if normalized_reason.startswith("playwright_error") or normalized_reason.startswith("qa_exception"):
        return True
    return normalized_reason == "runtime_console_error" and bool(fatal_rows)


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.QA_RUNTIME,
        agent_name=PipelineAgentName.QA_RUNTIME,
    )
    if gated_state is not None:
        return gated_state

    state["qa_attempt"] += 1

    # deterministic forced failures for controlled retry testing
    if state["qa_attempt"] <= state["fail_qa_until"]:
        state["needs_rebuild"] = False
        return append_log(
            state,
            stage=PipelineStage.QA_RUNTIME,
            status=PipelineStatus.SUCCESS,
            agent_name=PipelineAgentName.QA_RUNTIME,
            message="Runtime QA forced soft-fail for simulation.",
            reason="soft_fail",
            metadata={
                "attempt": state["qa_attempt"],
                "soft_fail": True,
                "deliverables": ["runtime_smoke_probe", "qa_improvement_queue_item"],
                "contract_status": "warn",
                "contribution_score": 3.4,
            },
        )

    artifact_html = str(state["outputs"].get("artifact_html", ""))
    append_log(
        state,
        stage=PipelineStage.QA_RUNTIME,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.QA_RUNTIME,
        message="Runtime QA smoke check started.",
        metadata={"attempt": state["qa_attempt"]},
    )
    artifact_files = state["outputs"].get("artifact_files")
    entrypoint_path = state["outputs"].get("entrypoint_path")
    artifact_path = state["outputs"].get("artifact_path")
    smoke_result = deps.quality_service.run_smoke_check(
        artifact_html,
        artifact_files=artifact_files if isinstance(artifact_files, list) else None,
        entrypoint_path=entrypoint_path if isinstance(entrypoint_path, str) else (artifact_path if isinstance(artifact_path, str) else None),
    )

    state["outputs"]["runtime_smoke_result"] = {
        "ok": smoke_result.ok,
        "reason": smoke_result.reason,
        "console_errors": smoke_result.console_errors or [],
        "fatal_errors": smoke_result.fatal_errors or [],
        "non_fatal_warnings": smoke_result.non_fatal_warnings or [],
        "visual_metrics": smoke_result.visual_metrics or {},
    }

    if not smoke_result.ok:
        fatal_errors = [str(item).strip() for item in smoke_result.fatal_errors or [] if str(item).strip()]
        non_fatal_warnings = [str(item).strip() for item in smoke_result.non_fatal_warnings or [] if str(item).strip()]
        critical_failure = _is_critical_runtime_failure(reason=smoke_result.reason, fatal_errors=fatal_errors)
        state["needs_rebuild"] = False
        state["outputs"].pop("qa_rebuild_feedback", None)
        queued_items = state["outputs"].get("qa_improvement_items")
        improvement_items = [row for row in queued_items if isinstance(row, dict)] if isinstance(queued_items, list) else []
        improvement_items.append(
            {
                "stage": PipelineStage.QA_RUNTIME.value,
                "reason": str(smoke_result.reason or "runtime_smoke_failed"),
                "severity": "high" if fatal_errors else "medium",
                "tokens": [
                    *fatal_errors,
                    *non_fatal_warnings,
                ],
                "metrics": {
                    "attempt": state["qa_attempt"],
                    "fatal_error_count": len(fatal_errors),
                    "warning_count": len(non_fatal_warnings),
                    "critical_failure": critical_failure,
                },
            }
        )
        state["outputs"]["qa_improvement_items"] = improvement_items
        state["outputs"]["qa_soft_fail"] = not critical_failure
        if critical_failure:
            state["status"] = PipelineStatus.ERROR
            state["reason"] = "runtime_system_failure"
            return append_log(
                state,
                stage=PipelineStage.QA_RUNTIME,
                status=PipelineStatus.ERROR,
                agent_name=PipelineAgentName.QA_RUNTIME,
                message="Runtime QA hard-fail: system-critical execution failure detected.",
                reason=state["reason"],
                metadata={
                    "attempt": state["qa_attempt"],
                    "critical_failure": True,
                    "console_errors": smoke_result.console_errors or [],
                    "fatal_errors": fatal_errors,
                    "non_fatal_warnings": non_fatal_warnings,
                    "deliverables": ["runtime_smoke_probe", "critical_failure_report"],
                    "contract_status": "fail",
                    "contribution_score": 1.5,
                },
            )

        return append_log(
            state,
            stage=PipelineStage.QA_RUNTIME,
            status=PipelineStatus.SUCCESS,
            agent_name=PipelineAgentName.QA_RUNTIME,
            message="Runtime QA soft-fail: improvement queued.",
            reason=str(smoke_result.reason or "runtime_smoke_failed"),
            metadata={
                "attempt": state["qa_attempt"],
                "soft_fail": True,
                "critical_failure": False,
                "console_errors": smoke_result.console_errors or [],
                "fatal_errors": fatal_errors,
                "non_fatal_warnings": non_fatal_warnings,
                "deliverables": ["runtime_smoke_probe", "qa_improvement_queue_item"],
                "contract_status": "warn",
                "contribution_score": 3.5,
            },
        )

    state["needs_rebuild"] = False
    state["outputs"].pop("qa_rebuild_feedback", None)

    if smoke_result.screenshot_bytes:
        game_slug = str(state["outputs"].get("game_slug", "untitled"))
        screenshot_url = deps.publisher_service.upload_screenshot(
            slug=game_slug,
            screenshot_bytes=smoke_result.screenshot_bytes,
        )
        if screenshot_url:
            state["outputs"]["screenshot_url"] = screenshot_url

    warning_count = len(smoke_result.non_fatal_warnings or [])
    runtime_message = "Runtime QA passed."
    if warning_count > 0:
        runtime_message = f"Runtime QA passed with {warning_count} warning{'s' if warning_count > 1 else ''}."

    return append_log(
        state,
        stage=PipelineStage.QA_RUNTIME,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.QA_RUNTIME,
        message=runtime_message,
        metadata={
            "attempt": state["qa_attempt"],
            "fatal_errors": smoke_result.fatal_errors or [],
            "non_fatal_warnings": smoke_result.non_fatal_warnings or [],
            "visual_metrics": smoke_result.visual_metrics or {},
            "deliverables": ["runtime_smoke_probe", "screenshot_capture"],
            "contract_status": "pass",
            "contribution_score": 4.1,
        },
    )
