from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import DesignSpecPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _derive_art_direction_contract(*, keyword: str, genre: str, visual_style: str) -> dict[str, object]:
    keyword_hint = keyword.casefold()
    motif = "neon-motion"
    if any(token in keyword_hint for token in ("판타지", "fantasy", "마법", "dungeon")):
        motif = "fantasy-arcane"
    elif any(token in keyword_hint for token in ("비행", "flight", "항공", "pilot")):
        motif = "aero-cinematic"
    elif any(token in keyword_hint for token in ("코믹", "comic", "brawler")):
        motif = "comic-impact"

    return {
        "style_tag": visual_style,
        "genre": genre,
        "motif": motif,
        "asset_strategy_mode": "procedural_threejs_first",
        "asset_provider": "builtin_vector_pack",
        "external_image_generation": False,
        "required_visual_keywords": [motif, "readable_silhouette", "high_contrast_hud"],
        "forbidden_visual_tokens": ["placeholder", "temp", "debug-ui", "plain-rectangle-only"],
        "min_image_assets": 5,
        "min_render_layers": 4,
        "min_animation_hooks": 3,
        "min_procedural_layers": 3,
    }


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gdd_output = state["outputs"].get("gdd", {})
    visual_style = str(gdd_output.get("visual_style", "neon-minimal"))
    keyword = state["keyword"]
    genre = str(gdd_output.get("genre", "arcade"))
    generated = deps.vertex_service.generate_design_spec(keyword=keyword, visual_style=visual_style, genre=genre)
    try:
        design_spec = DesignSpecPayload.model_validate(generated.payload)
    except Exception:
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
    art_direction_contract = _derive_art_direction_contract(
        keyword=keyword,
        genre=genre,
        visual_style=design_spec.visual_style,
    )
    state["outputs"]["design_spec"] = design_spec.model_dump()
    state["outputs"]["art_direction_contract"] = art_direction_contract
    return append_log(
        state,
        stage=PipelineStage.STYLE,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.STYLIST,
        message="Design spec + art direction contract generated.",
        metadata={
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
            "min_font_size_px": design_spec.min_font_size_px,
            "overflow_policy": design_spec.text_overflow_policy,
            "art_motif": art_direction_contract.get("motif"),
            "min_image_assets": art_direction_contract.get("min_image_assets"),
            **generated.meta,
        },
    )
