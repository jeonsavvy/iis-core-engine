from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import DesignSpecPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def run(state: PipelineState, _deps: NodeDependencies) -> PipelineState:
    visual_style = state["outputs"].get("gdd", {}).get("visual_style", "neon-minimal")
    design_spec = DesignSpecPayload(
        visual_style=visual_style,
        palette=["#0EA5E9", "#111827", "#22C55E", "#F8FAFC"],
        hud="score-top-left / timer-top-right / combo-bottom",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=24,
        min_font_size_px=14,
        text_overflow_policy="ellipsis-clamp",
        typography="inter-bold-hud",
        thumbnail_concept="Neon particle burst with score counter.",
    )
    state["outputs"]["design_spec"] = design_spec.model_dump()
    return append_log(
        state,
        stage=PipelineStage.STYLE,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.STYLIST,
        message="Design spec JSON generated with viewport/safe-area/text policy.",
        metadata={
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
            "min_font_size_px": design_spec.min_font_size_px,
            "overflow_policy": design_spec.text_overflow_policy,
        },
    )
