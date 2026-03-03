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
    settings = deps.vertex_service.settings
    strict_vertex_only = bool(getattr(settings, "strict_vertex_only", True))
    generated = deps.vertex_service.generate_design_spec(keyword=keyword, visual_style=visual_style, genre=genre)
    design_spec_source = str(generated.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and design_spec_source != "vertex":
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "design_spec_unavailable"
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 중단: Vertex design spec을 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "design_spec_source": design_spec_source,
                "strict_vertex_only": strict_vertex_only,
                "deliverables": ["design_spec_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
        )
    try:
        design_spec = DesignSpecPayload.model_validate(generated.payload)
    except Exception:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "design_spec_invalid"
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 중단: design spec payload 검증 실패.",
            reason=state["reason"],
            metadata={
                "design_spec_source": design_spec_source,
                "strict_vertex_only": strict_vertex_only,
                "deliverables": ["design_spec_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
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
    design_contract_source = str(generated_contract.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and design_contract_source != "vertex":
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "design_contract_unavailable"
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 중단: Vertex design contract를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "design_spec_source": design_spec_source,
                "design_contract_source": design_contract_source,
                "strict_vertex_only": strict_vertex_only,
                "deliverables": ["design_contract_gate"],
                "contract_status": "fail",
                **generated_contract.meta,
            },
        )
    try:
        design_contract = DesignContractPayload.model_validate(generated_contract.payload)
    except Exception:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "design_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 중단: design contract payload 검증 실패.",
            reason=state["reason"],
            metadata={
                "design_spec_source": design_spec_source,
                "design_contract_source": design_contract_source,
                "strict_vertex_only": strict_vertex_only,
                "deliverables": ["design_contract_gate"],
                "contract_status": "fail",
                **generated_contract.meta,
            },
        )
    state["outputs"]["design_spec"] = design_spec.model_dump()
    state["outputs"]["art_direction_contract"] = art_direction_contract
    state["outputs"]["design_contract"] = design_contract.model_dump()
    state["outputs"]["design_spec_source"] = design_spec_source
    state["outputs"]["design_spec_meta"] = dict(generated.meta)
    state["outputs"]["design_contract_source"] = design_contract_source
    state["outputs"]["design_contract_meta"] = dict(generated_contract.meta)
    design_spec_usage = generated.meta.get("usage", {}) if isinstance(generated.meta.get("usage", {}), dict) else {}
    design_contract_usage = (
        generated_contract.meta.get("usage", {}) if isinstance(generated_contract.meta.get("usage", {}), dict) else {}
    )
    usage = {
        "prompt_tokens": int(design_spec_usage.get("prompt_tokens", 0) or 0)
        + int(design_contract_usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(design_spec_usage.get("completion_tokens", 0) or 0)
        + int(design_contract_usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(design_spec_usage.get("total_tokens", 0) or 0)
        + int(design_contract_usage.get("total_tokens", 0) or 0),
    }
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
            "strict_vertex_only": strict_vertex_only,
            "design_spec_source": design_spec_source,
            "design_contract_source": design_contract_source,
            "design_spec_usage": design_spec_usage,
            "design_contract_usage": design_contract_usage,
            "usage": usage,
            "model": str(generated_contract.meta.get("model") or generated.meta.get("model") or "").strip() or None,
        },
    )
