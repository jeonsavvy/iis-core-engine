from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    state["qa_attempt"] += 1

    # deterministic forced failures for controlled retry testing
    if state["qa_attempt"] <= state["fail_qa_until"]:
        state["needs_rebuild"] = True
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
    smoke_result = deps.quality_service.run_smoke_check(artifact_html)

    if not smoke_result.ok:
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
                "console_errors": smoke_result.console_errors or [],
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

    state["needs_rebuild"] = False
    qa_message = "QA passed via Playwright smoke check and quality/gameplay gates."
    if smoke_result.reason:
        qa_message = f"QA passed with fallback: {smoke_result.reason}"

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
            "quality_score": quality_result.score,
            "quality_threshold": quality_result.threshold,
            "gameplay_score": gameplay_result.score,
            "gameplay_threshold": gameplay_result.threshold,
            "checks": quality_result.checks,
            "gameplay_checks": gameplay_result.checks,
        },
    )
