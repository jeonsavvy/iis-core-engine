from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, _deps: NodeDependencies) -> PipelineState:
    state["status"] = PipelineStatus.ERROR
    state["reason"] = f"QA failed after {state['qa_attempt']} attempts"
    return append_log(
        state,
        stage=PipelineStage.QA_RUNTIME,
        status=PipelineStatus.ERROR,
        agent_name=PipelineAgentName.QA_RUNTIME,
        message="Pipeline stopped because QA retry budget was exhausted.",
        reason=state["reason"],
    )
