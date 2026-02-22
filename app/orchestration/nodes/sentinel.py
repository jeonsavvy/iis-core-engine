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
            },
        )

    state["needs_rebuild"] = False
    qa_message = "QA passed via Playwright smoke check and quality gate."
    if smoke_result.reason:
        qa_message = f"QA passed with fallback: {smoke_result.reason}"

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
        },
    )
