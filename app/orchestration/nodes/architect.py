from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.PLAN,
        agent_name=PipelineAgentName.ARCHITECT,
    )
    if gated_state is not None:
        return gated_state

    keyword = state["keyword"]
    generated = deps.vertex_service.generate_gdd_bundle(keyword)
    payload = generated.payload
    try:
        gdd = GDDPayload.model_validate(payload.get("gdd", {}))
    except Exception:
        gdd = GDDPayload(
            title=f"{keyword.title()} Infinite",
            genre="arcade",
            objective="Get highest score possible in 90 seconds.",
            visual_style="neon-minimal",
        )
    raw_research = payload.get("research_summary")
    if isinstance(raw_research, dict):
        references = raw_research.get("references")
        reference_list = [str(item) for item in references[:8]] if isinstance(references, list) else []
        intent = raw_research.get("intent")
        research_summary = {
            "intent": str(intent) if isinstance(intent, str) and intent.strip() else f"{keyword} 기반 코어 플레이 루프 아이디어 수집",
            "references": reference_list
            or [
                f"{keyword} + score-attack progression",
                f"{keyword} + 90-second arcade pacing",
                f"{keyword} + mobile-friendly HUD readability",
            ],
        }
    else:
        research_summary = {
            "intent": f"{keyword} 기반 코어 플레이 루프 아이디어 수집",
            "references": [
                f"{keyword} + score-attack progression",
                f"{keyword} + 90-second arcade pacing",
                f"{keyword} + mobile-friendly HUD readability",
            ],
        }
    state["outputs"]["research_summary"] = research_summary
    state["outputs"]["gdd"] = gdd.model_dump()
    meta = {"reference_count": len(research_summary["references"]), **generated.meta}
    return append_log(
        state,
        stage=PipelineStage.PLAN,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.ARCHITECT,
        message="Planner+Researcher generated GDD and reference summary.",
        metadata=meta,
    )
