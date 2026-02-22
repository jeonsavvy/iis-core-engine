from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    slug = state["outputs"].get("game_slug", "unknown-game")
    result = deps.x_service.publish_update(
        game_slug=slug,
        text=f"New game launched: {slug} #indiegame #html5",
    )

    status = PipelineStatus.SUCCESS if result.get("status") == "posted" else PipelineStatus.SKIPPED
    reason = result.get("reason")

    state = append_log(
        state,
        stage=PipelineStage.ECHO,
        status=status,
        agent_name=PipelineAgentName.ECHO,
        message=f"X posting result: {result.get('status', 'unknown')}",
        reason=reason,
    )

    if state["status"] != PipelineStatus.ERROR:
        state["status"] = PipelineStatus.SUCCESS
        append_log(
            state,
            stage=PipelineStage.DONE,
            status=PipelineStatus.SUCCESS,
            agent_name=PipelineAgentName.ECHO,
            message="Pipeline finished.",
        )
    return state
