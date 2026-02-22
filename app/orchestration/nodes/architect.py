from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, _deps: NodeDependencies) -> PipelineState:
    keyword = state["keyword"]
    research_summary = {
        "intent": f"{keyword} 기반 코어 플레이 루프 아이디어 수집",
        "references": [
            f"{keyword} + score-attack progression",
            f"{keyword} + 90-second arcade pacing",
            f"{keyword} + mobile-friendly HUD readability",
        ],
    }
    gdd = GDDPayload(
        title=f"{keyword.title()} Infinite",
        genre="arcade",
        objective="Get highest score possible in 90 seconds.",
        visual_style="neon-minimal",
    )
    state["outputs"]["research_summary"] = research_summary
    state["outputs"]["gdd"] = gdd.model_dump()
    return append_log(
        state,
        stage=PipelineStage.PLAN,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.ARCHITECT,
        message="Planner+Researcher generated GDD and reference summary.",
        metadata={"reference_count": len(research_summary["references"])},
    )
