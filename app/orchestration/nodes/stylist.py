from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate, classify_vertex_unavailable_reason
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import DesignContractPayload, DesignSpecPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus
from app.services.shared_generation_contract import (
    compute_shared_generation_contract_hash,
    merge_shared_generation_contract,
    validate_shared_generation_contract,
)


def _validation_error_detail(exc: Exception) -> object:
    if isinstance(exc, ValidationError):
        return exc.errors()
    return str(exc)


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

    resume_stage = str(state["outputs"].get("resume_stage", "")).strip().casefold()
    if resume_stage in {"build", "qa_runtime", "qa_quality", "release", "report"}:
        cached_spec = state["outputs"].get("design_spec")
        cached_contract = state["outputs"].get("design_contract")
        if isinstance(cached_spec, dict) and cached_spec and isinstance(cached_contract, dict) and cached_contract:
            state["status"] = PipelineStatus.RUNNING
            return append_log(
                state,
                stage=PipelineStage.DESIGN,
                status=PipelineStatus.SUCCESS,
                agent_name=PipelineAgentName.DESIGNER,
                message="디자인 재개: 기존 design spec/contract를 재사용합니다.",
                metadata={
                    "resume_stage": resume_stage,
                    "reused_cached_contract": True,
                    "contract_status": "pass",
                },
            )

    gdd_output = state["outputs"].get("gdd", {})
    visual_style = str(gdd_output.get("visual_style", "neon-minimal"))
    keyword = state["keyword"]
    genre = str(gdd_output.get("genre", "arcade"))
    settings = deps.vertex_service.settings
    strict_vertex_only = bool(getattr(settings, "strict_vertex_only", True))
    shared_contract = state["outputs"].get("shared_generation_contract")
    typed_shared_contract = shared_contract if isinstance(shared_contract, dict) else None
    shared_contract_issues = validate_shared_generation_contract(typed_shared_contract)
    if shared_contract_issues:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "shared_generation_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 중단: 공유 생성 계약이 유효하지 않습니다.",
            reason=state["reason"],
            metadata={
                "shared_generation_contract_issues": shared_contract_issues,
                "deliverables": ["shared_generation_contract_gate"],
                "contract_status": "fail",
            },
        )

    try:
        generated = deps.vertex_service.generate_design_spec(
            keyword=keyword,
            visual_style=visual_style,
            genre=genre,
            shared_contract=typed_shared_contract,
        )
    except TypeError:
        generated = deps.vertex_service.generate_design_spec(keyword=keyword, visual_style=visual_style, genre=genre)
    design_spec_source = str(generated.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and design_spec_source != "vertex":
        reason, retryable = classify_vertex_unavailable_reason(
            default_reason="design_spec_unavailable",
            generation_meta=generated.meta,
        )
        state["reason"] = reason
        state["status"] = PipelineStatus.RETRY if retryable else PipelineStatus.ERROR
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=state["status"],
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 지연: Vertex design spec을 확보하지 못했습니다."
            if retryable
            else "디자인 중단: Vertex design spec을 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "design_spec_source": design_spec_source,
                "strict_vertex_only": strict_vertex_only,
                "retryable": retryable,
                "upstream_reason": str(generated.meta.get("reason", "")).strip() or None,
                "vertex_error": str(generated.meta.get("vertex_error", "")).strip() or None,
                "deliverables": ["design_spec_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
        )
    try:
        design_spec = DesignSpecPayload.model_validate(generated.payload)
    except Exception as exc:
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
                "validation_error": _validation_error_detail(exc),
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
    try:
        generated_contract = deps.vertex_service.generate_design_contract(
            keyword=keyword,
            genre=genre,
            visual_style=design_spec.visual_style,
            design_spec=design_spec.model_dump(),
            shared_contract=typed_shared_contract,
        )
    except TypeError:
        generated_contract = deps.vertex_service.generate_design_contract(
            keyword=keyword,
            genre=genre,
            visual_style=design_spec.visual_style,
            design_spec=design_spec.model_dump(),
        )
    design_contract_source = str(generated_contract.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and design_contract_source != "vertex":
        reason, retryable = classify_vertex_unavailable_reason(
            default_reason="design_contract_unavailable",
            generation_meta=generated_contract.meta,
        )
        state["reason"] = reason
        state["status"] = PipelineStatus.RETRY if retryable else PipelineStatus.ERROR
        return append_log(
            state,
            stage=PipelineStage.DESIGN,
            status=state["status"],
            agent_name=PipelineAgentName.DESIGNER,
            message="디자인 지연: Vertex design contract를 확보하지 못했습니다."
            if retryable
            else "디자인 중단: Vertex design contract를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "design_spec_source": design_spec_source,
                "design_contract_source": design_contract_source,
                "strict_vertex_only": strict_vertex_only,
                "retryable": retryable,
                "upstream_reason": str(generated_contract.meta.get("reason", "")).strip() or None,
                "vertex_error": str(generated_contract.meta.get("vertex_error", "")).strip() or None,
                "deliverables": ["design_contract_gate"],
                "contract_status": "fail",
                **generated_contract.meta,
            },
        )
    try:
        design_contract = DesignContractPayload.model_validate(generated_contract.payload)
    except Exception as exc:
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
                "validation_error": _validation_error_detail(exc),
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
    shared_contract = merge_shared_generation_contract(
        contract=typed_shared_contract,
        keyword=keyword,
        runtime_engine_mode=None,
        visual_profile_hint=genre,
    )
    shared_contract_hash = compute_shared_generation_contract_hash(shared_contract)
    state["outputs"]["shared_generation_contract"] = shared_contract
    state["outputs"]["shared_generation_contract_hash"] = shared_contract_hash
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
            "shared_generation_contract_hash": shared_contract_hash,
            "strict_vertex_only": strict_vertex_only,
            "design_spec_source": design_spec_source,
            "design_contract_source": design_contract_source,
            "design_spec_usage": design_spec_usage,
            "design_contract_usage": design_contract_usage,
            "usage": usage,
            "model": str(generated_contract.meta.get("model") or generated.meta.get("model") or "").strip() or None,
        },
    )
