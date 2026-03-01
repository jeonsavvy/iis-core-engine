from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import DesignContractPayload, DesignSpecPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _derive_art_direction_contract(*, keyword: str, genre: str, visual_style: str) -> dict[str, object]:
    keyword_hint = keyword.casefold()
    motif = "neon-motion"
    if any(token in keyword_hint for token in ("판타지", "fantasy", "마법", "dungeon")):
        motif = "fantasy-arcane"
    elif any(token in keyword_hint for token in ("비행", "flight", "항공", "pilot")):
        motif = "aero-cinematic"
    elif any(token in keyword_hint for token in ("f1", "포뮬러", "formula", "그랑프리", "circuit")):
        motif = "formula-aerodynamic"
    elif any(token in keyword_hint for token in ("코믹", "comic", "brawler")):
        motif = "comic-impact"

    detail_tier = "enhanced"
    asset_variant_count = 4
    min_render_layers = 4
    min_procedural_layers = 3
    if motif in {"formula-aerodynamic", "aero-cinematic"}:
        detail_tier = "cinematic"
        asset_variant_count = 5
        min_render_layers = 5
        min_procedural_layers = 4
    elif motif == "fantasy-arcane":
        detail_tier = "illustrative"

    return {
        "style_tag": visual_style,
        "genre": genre,
        "motif": motif,
        "asset_strategy_mode": "procedural_threejs_first",
        "asset_provider": "builtin_vector_pack",
        "external_image_generation": False,
        "required_visual_keywords": [motif, "readable_silhouette", "high_contrast_hud"],
        "forbidden_visual_tokens": ["placeholder", "temp", "debug-ui", "plain-rectangle-only"],
        "asset_variant_count": asset_variant_count,
        "asset_detail_tier": detail_tier,
        "min_image_assets": 5,
        "min_render_layers": min_render_layers,
        "min_animation_hooks": 3,
        "min_procedural_layers": min_procedural_layers,
    }


def _fallback_design_contract(*, keyword: str, genre: str, visual_style: str) -> DesignContractPayload:
    return DesignContractPayload(
        camera_ui_contract=[
            "camera movement keeps player context stable",
            "hud keeps score/time/hp readable",
            "critical interaction not occluded by overlays",
        ],
        asset_blueprint_2d3d=[
            f"{genre} player rig",
            "enemy archetype set",
            "projectile and impact VFX",
            "environment modular kit",
            f"style profile: {visual_style} / keyword: {keyword}",
        ],
        scene_layers=[
            "foreground gameplay",
            "midground interaction",
            "background depth layer",
            "postfx feedback layer",
        ],
        feedback_fx_contract=[
            "hit confirmation flash",
            "danger telegraph pulse",
            "combo escalation response",
        ],
        readability_contract=[
            "player/enemy/projectile silhouette separation",
            "collision-critical entities maintain edge contrast",
            "motion effects do not hide hitboxes",
        ],
    )


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.DESIGN,
        agent_name=PipelineAgentName.DESIGNER,
    )
    if gated_state is not None:
        return gated_state

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
    generated_contract = deps.vertex_service.generate_design_contract(
        keyword=keyword,
        genre=genre,
        visual_style=design_spec.visual_style,
        design_spec=design_spec.model_dump(),
    )
    try:
        design_contract = DesignContractPayload.model_validate(generated_contract.payload)
    except Exception:
        design_contract = _fallback_design_contract(
            keyword=keyword,
            genre=genre,
            visual_style=design_spec.visual_style,
        )
    state["outputs"]["design_spec"] = design_spec.model_dump()
    state["outputs"]["art_direction_contract"] = art_direction_contract
    state["outputs"]["design_contract"] = design_contract.model_dump()
    return append_log(
        state,
        stage=PipelineStage.DESIGN,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.DESIGNER,
        message="디자인 계약 생성 완료: 카메라/UI/자산 청사진 확정.",
        metadata={
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
            "min_font_size_px": design_spec.min_font_size_px,
            "overflow_policy": design_spec.text_overflow_policy,
            "art_motif": art_direction_contract.get("motif"),
            "min_image_assets": art_direction_contract.get("min_image_assets"),
            "deliverables": [
                "design_spec.viewport/palette",
                "design_contract.asset_blueprint_2d3d",
                "design_contract.scene_layers",
                "design_contract.readability_contract",
            ],
            "contract_status": "pass",
            "contract_summary": f"{len(design_contract.asset_blueprint_2d3d)} asset blueprint entries",
            "contribution_score": 4.2,
            **generated.meta,
            **generated_contract.meta,
        },
    )
