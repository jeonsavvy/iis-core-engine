from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, _deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        _deps,
        stage=PipelineStage.TRIGGER,
        agent_name=PipelineAgentName.TRIGGER,
        allow_pause=False,
    )
    if gated_state is not None:
        return gated_state

    state["status"] = PipelineStatus.RUNNING
    pipeline_version = str(state["outputs"].get("pipeline_version", "forgeflow-v1"))
    return append_log(
        state,
        stage=PipelineStage.TRIGGER,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.TRIGGER,
        message=f"Director accepted trigger keyword: {state['keyword']}",
        metadata={"pipeline_version": pipeline_version},
    )
