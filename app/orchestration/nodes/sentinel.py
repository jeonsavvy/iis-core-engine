from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.QA,
        agent_name=PipelineAgentName.SENTINEL,
    )
    if gated_state is not None:
        return gated_state

    state["qa_attempt"] += 1

    def _set_rebuild_feedback(
        *,
        gate: str,
        reason: str,
        failed_checks: list[str] | None = None,
        fatal_errors: list[str] | None = None,
        non_fatal_warnings: list[str] | None = None,
    ) -> None:
        state["outputs"]["qa_rebuild_feedback"] = {
            "gate": gate,
            "reason": reason,
            "qa_attempt": state["qa_attempt"],
            "failed_checks": [str(item).strip() for item in (failed_checks or []) if str(item).strip()],
            "fatal_errors": [str(item).strip() for item in (fatal_errors or []) if str(item).strip()],
            "non_fatal_warnings": [str(item).strip() for item in (non_fatal_warnings or []) if str(item).strip()],
        }

    # deterministic forced failures for controlled retry testing
    if state["qa_attempt"] <= state["fail_qa_until"]:
        state["needs_rebuild"] = True
        state["outputs"].pop("qa_rebuild_feedback", None)
        return append_log(
            state,
            stage=PipelineStage.QA,
            status=PipelineStatus.RETRY,
            agent_name=PipelineAgentName.SENTINEL,
            message="QA forced failure for retry simulation.",
            reason="retry_builder",
            metadata={"attempt": state["qa_attempt"]},
        )

    artifact_html = str(state["outputs"].get("artifact_html", ""))
    append_log(
        state,
        stage=PipelineStage.QA,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.SENTINEL,
        message="Playwright smoke check started.",
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
    runtime_guard = state["outputs"].get("builder_runtime_guard")
    runtime_guard_choice = ""
    if isinstance(runtime_guard, dict):
        chosen = runtime_guard.get("chosen")
        if isinstance(chosen, str):
            runtime_guard_choice = chosen.strip().lower()

    smoke_soft_fail = False

    if not smoke_result.ok:
        if smoke_result.reason == "runtime_console_error" and runtime_guard_choice in {"polished", "selected", "baseline"}:
            smoke_soft_fail = True
            append_log(
                state,
                stage=PipelineStage.QA,
                status=PipelineStatus.RUNNING,
                agent_name=PipelineAgentName.SENTINEL,
                message="QA warning: runtime console error tolerated (builder runtime guard passed).",
                reason=smoke_result.reason,
                metadata={
                    "attempt": state["qa_attempt"],
                    "runtime_guard_choice": runtime_guard_choice,
                    "fatal_errors": smoke_result.fatal_errors or [],
                    "non_fatal_warnings": smoke_result.non_fatal_warnings or [],
                },
            )
        else:
            _set_rebuild_feedback(
                gate="runtime",
                reason=str(smoke_result.reason or "runtime_console_error"),
                fatal_errors=smoke_result.fatal_errors or [],
                non_fatal_warnings=smoke_result.non_fatal_warnings or [],
            )
            state["needs_rebuild"] = True
            return append_log(
                state,
                stage=PipelineStage.QA,
                status=PipelineStatus.RETRY,
                agent_name=PipelineAgentName.SENTINEL,
                message="QA failed: runtime error detected in Playwright smoke check.",
                reason=smoke_result.reason,
                metadata={
                    "attempt": state["qa_attempt"],
                    "runtime_guard_choice": runtime_guard_choice or None,
                    "console_errors": smoke_result.console_errors or [],
                    "fatal_errors": smoke_result.fatal_errors or [],
                    "non_fatal_warnings": smoke_result.non_fatal_warnings or [],
                },
            )

    design_spec = state["outputs"].get("design_spec", {})
    append_log(
        state,
        stage=PipelineStage.QA,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.SENTINEL,
        message="Quality + gameplay gate evaluation started.",
        metadata={"attempt": state["qa_attempt"]},
    )
    quality_result = deps.quality_service.evaluate_quality_contract(
        artifact_html,
        design_spec=design_spec if isinstance(design_spec, dict) else None,
    )
    if not quality_result.ok:
        _set_rebuild_feedback(
            gate="quality",
            reason="quality_score_below_threshold",
            failed_checks=quality_result.failed_checks,
        )
        state["needs_rebuild"] = True
        return append_log(
            state,
            stage=PipelineStage.QA,
            status=PipelineStatus.RETRY,
            agent_name=PipelineAgentName.SENTINEL,
            message="QA failed: quality score below threshold.",
            reason="quality_score_below_threshold",
            metadata={
                "attempt": state["qa_attempt"],
                "quality_score": quality_result.score,
                "quality_threshold": quality_result.threshold,
                "failed_checks": quality_result.failed_checks,
                "checks": quality_result.checks,
            },
        )

    gameplay_result = deps.quality_service.evaluate_gameplay_gate(
        artifact_html,
        design_spec=design_spec if isinstance(design_spec, dict) else None,
        genre=str(state["outputs"].get("game_genre", "")),
        genre_engine=str(state["outputs"].get("genre_engine", "")),
        keyword=str(state.get("keyword", "")),
    )
    if not gameplay_result.ok:
        _set_rebuild_feedback(
            gate="gameplay",
            reason="gameplay_depth_below_threshold",
            failed_checks=gameplay_result.failed_checks,
        )
        state["needs_rebuild"] = True
        return append_log(
            state,
            stage=PipelineStage.QA,
            status=PipelineStatus.RETRY,
            agent_name=PipelineAgentName.SENTINEL,
            message="QA failed: gameplay depth score below threshold.",
            reason="gameplay_depth_below_threshold",
            metadata={
                "attempt": state["qa_attempt"],
                "gameplay_score": gameplay_result.score,
                "gameplay_threshold": gameplay_result.threshold,
                "failed_checks": gameplay_result.failed_checks,
                "checks": gameplay_result.checks,
            },
        )

    visual_result = deps.quality_service.evaluate_visual_gate(
        smoke_result.visual_metrics,
        genre_engine=str(state["outputs"].get("genre_engine", "")),
    )
    visual_gate_soft_fail = False
    visual_retry_budget = 1
    visual_retry_count = int(state["outputs"].get("visual_retry_count", 0) or 0)
    if not visual_result.ok:
        state["outputs"]["qa_visual_feedback"] = {
            "score": visual_result.score,
            "threshold": visual_result.threshold,
            "failed_checks": visual_result.failed_checks,
            "checks": visual_result.checks,
            "visual_metrics": smoke_result.visual_metrics or {},
        }
        if visual_retry_count < visual_retry_budget:
            _set_rebuild_feedback(
                gate="visual",
                reason="visual_quality_below_threshold",
                failed_checks=visual_result.failed_checks,
            )
            state["outputs"]["visual_retry_count"] = visual_retry_count + 1
            state["needs_rebuild"] = True
            return append_log(
                state,
                stage=PipelineStage.QA,
                status=PipelineStatus.RETRY,
                agent_name=PipelineAgentName.SENTINEL,
                message="QA 재작업: 시각 품질 보완 요청을 빌드 단계로 전달합니다.",
                reason="visual_quality_below_threshold",
                metadata={
                    "attempt": state["qa_attempt"],
                    "visual_score": visual_result.score,
                    "visual_threshold": visual_result.threshold,
                    "failed_checks": visual_result.failed_checks,
                    "checks": visual_result.checks,
                    "visual_metrics": smoke_result.visual_metrics or {},
                    "visual_retry_count": visual_retry_count + 1,
                    "visual_retry_budget": visual_retry_budget,
                },
            )

        visual_gate_soft_fail = True
        append_log(
            state,
            stage=PipelineStage.QA,
            status=PipelineStatus.RUNNING,
            agent_name=PipelineAgentName.SENTINEL,
            message="QA warning: visual quality score below threshold (soft-fail).",
            reason="visual_quality_below_threshold",
            metadata={
                "attempt": state["qa_attempt"],
                "visual_score": visual_result.score,
                "visual_threshold": visual_result.threshold,
                "failed_checks": visual_result.failed_checks,
                "checks": visual_result.checks,
                "visual_metrics": smoke_result.visual_metrics or {},
                "visual_retry_count": visual_retry_count,
                "visual_retry_budget": visual_retry_budget,
            },
        )
    else:
        state["outputs"]["visual_retry_count"] = 0
        state["outputs"].pop("qa_visual_feedback", None)

    artifact_result = deps.quality_service.evaluate_artifact_contract(
        state["outputs"].get("artifact_manifest") if isinstance(state["outputs"].get("artifact_manifest"), dict) else None,
        art_direction_contract=state["outputs"].get("art_direction_contract")
        if isinstance(state["outputs"].get("art_direction_contract"), dict)
        else None,
    )
    if not artifact_result.ok:
        _set_rebuild_feedback(
            gate="artifact",
            reason="artifact_contract_below_threshold",
            failed_checks=artifact_result.failed_checks,
        )
        state["needs_rebuild"] = True
        return append_log(
            state,
            stage=PipelineStage.QA,
            status=PipelineStatus.RETRY,
            agent_name=PipelineAgentName.SENTINEL,
            message="QA failed: artifact contract gate below threshold.",
            reason="artifact_contract_below_threshold",
            metadata={
                "attempt": state["qa_attempt"],
                "artifact_score": artifact_result.score,
                "artifact_threshold": artifact_result.threshold,
                "failed_checks": artifact_result.failed_checks,
                "checks": artifact_result.checks,
            },
        )

    state["needs_rebuild"] = False
    state["outputs"].pop("qa_rebuild_feedback", None)
    qa_message = "QA passed via Playwright smoke check and quality/gameplay gates."
    if smoke_result.reason:
        qa_message = f"QA passed with fallback: {smoke_result.reason}"
    warning_count = len(smoke_result.non_fatal_warnings or [])
    if warning_count > 0:
        qa_message += f" ({warning_count} runtime warning{'s' if warning_count > 1 else ''})"
    if visual_gate_soft_fail:
        qa_message += " (visual gate soft-fail)"

    screenshot_url = None
    if smoke_result.screenshot_bytes:
        game_slug = str(state["outputs"].get("game_slug", "untitled"))
        screenshot_url = deps.publisher_service.upload_screenshot(
            slug=game_slug, 
            screenshot_bytes=smoke_result.screenshot_bytes
        )
        if screenshot_url:
            state["outputs"]["screenshot_url"] = screenshot_url
            qa_message += " (Screenshot captured)"

    return append_log(
        state,
        stage=PipelineStage.QA,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.SENTINEL,
        message=qa_message,
        metadata={
            "attempt": state["qa_attempt"],
            "smoke_soft_fail": smoke_soft_fail,
            "runtime_guard_choice": runtime_guard_choice or None,
            "quality_score": quality_result.score,
            "quality_threshold": quality_result.threshold,
            "gameplay_score": gameplay_result.score,
            "gameplay_threshold": gameplay_result.threshold,
            "visual_score": visual_result.score,
            "visual_threshold": visual_result.threshold,
            "visual_gate_soft_fail": visual_gate_soft_fail,
            "visual_failed_checks": visual_result.failed_checks,
            "artifact_score": artifact_result.score,
            "artifact_threshold": artifact_result.threshold,
            "checks": quality_result.checks,
            "gameplay_checks": gameplay_result.checks,
            "visual_checks": visual_result.checks,
            "artifact_checks": artifact_result.checks,
            "visual_metrics": smoke_result.visual_metrics or {},
            "fatal_errors": smoke_result.fatal_errors or [],
            "non_fatal_warnings": smoke_result.non_fatal_warnings or [],
        },
    )
