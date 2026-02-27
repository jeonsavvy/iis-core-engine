from __future__ import annotations

from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.builder_parts.assets import _build_hybrid_asset_bank, _resolve_asset_pack
from app.orchestration.nodes.builder_parts.bundle import _extract_hybrid_bundle_from_inline_html
from app.orchestration.nodes.builder_parts.html_runtime import _build_hybrid_engine_html
from app.orchestration.nodes.builder_parts.mode import (
    _detect_unsupported_scope,
    _infer_core_loop_type,
    _is_safe_slug,
    _slugify,
)
from app.orchestration.nodes.builder_parts.production_pipeline import build_production_artifact
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus

__all__ = [
    "run",
    "_build_hybrid_asset_bank",
    "_resolve_asset_pack",
    "_extract_hybrid_bundle_from_inline_html",
    "_build_hybrid_engine_html",
    "_infer_core_loop_type",
]


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.BUILD,
        agent_name=PipelineAgentName.BUILDER,
    )
    if gated_state is not None:
        return gated_state

    state["build_iteration"] += 1

    try:
        gdd = GDDPayload.model_validate(state["outputs"].get("gdd", {}))
    except ValidationError:
        gdd = GDDPayload(
            title=f"{state['keyword'].title()} Infinite",
            genre="arcade",
            objective="Survive escalating pressure while chaining skill actions for a high score.",
            visual_style="neon-minimal",
        )

    try:
        design_spec = DesignSpecPayload.model_validate(state["outputs"].get("design_spec", {}))
    except ValidationError:
        design_spec = DesignSpecPayload(
            visual_style=gdd.visual_style or "neon-minimal",
            palette=["#22C55E"],
            hud="score-top-left / timer-top-right",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
        )

    title = gdd.title
    genre = gdd.genre
    safe_slug = state["outputs"].get("safe_slug")
    if isinstance(safe_slug, str) and safe_slug and _is_safe_slug(safe_slug):
        slug = safe_slug
    else:
        slug = _slugify(state["keyword"])

    palette = design_spec.palette
    accent_color = str(palette[0]) if palette else "#22C55E"
    core_loop_type = _infer_core_loop_type(keyword=state["keyword"], title=title, genre=genre)
    unsupported_scope_reason = _detect_unsupported_scope(keyword=state["keyword"], title=title, genre=genre)
    if unsupported_scope_reason and deps.vertex_service.settings.builder_scope_guard_enabled:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = unsupported_scope_reason
        state["outputs"]["scope_guard_reason"] = unsupported_scope_reason
        state["outputs"]["requested_keyword"] = state["keyword"]
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.BUILDER,
            message="빌드 중단: 현재 파이프라인 범위를 초과한 요청입니다.",
            reason=unsupported_scope_reason,
            metadata={
                "keyword": state["keyword"],
                "title": title,
                "genre": genre,
                "supported_modes": [
                    "f1_formula_circuit_3d",
                    "flight_sim_3d",
                    "webgl_three_runner",
                    "topdown_roguelike_shooter",
                    "comic_action_brawler_3d",
                    "lane_dodge_racer",
                    "arena_shooter",
                    "duel_brawler",
                    "arcade_generic",
                ],
            },
        )

    asset_pack = _resolve_asset_pack(core_loop_type=core_loop_type, palette=palette)
    art_direction_contract = state["outputs"].get("art_direction_contract")
    if not isinstance(art_direction_contract, dict):
        art_direction_contract = {}

    asset_bank_files, runtime_asset_manifest = _build_hybrid_asset_bank(
        slug=slug,
        core_loop_type=core_loop_type,
        asset_pack=asset_pack,
        art_direction_contract=art_direction_contract,
    )
    contract = runtime_asset_manifest.get("contract")
    if isinstance(contract, dict):
        for key in ("min_image_assets", "min_render_layers", "min_animation_hooks", "min_procedural_layers"):
            value = art_direction_contract.get(key)
            if isinstance(value, int) and value > 0:
                contract[key] = int(value)
    policy = runtime_asset_manifest.get("asset_policy")
    if isinstance(policy, dict):
        mode_value = art_direction_contract.get("asset_strategy_mode")
        if isinstance(mode_value, str) and mode_value.strip():
            policy["mode"] = mode_value.strip()
        provider_value = art_direction_contract.get("asset_provider")
        if isinstance(provider_value, str) and provider_value.strip():
            policy["provider"] = provider_value.strip()
        external_generation = art_direction_contract.get("external_image_generation")
        if isinstance(external_generation, bool):
            policy["external_image_generation"] = external_generation
    if art_direction_contract:
        runtime_asset_manifest["art_direction"] = {
            key: art_direction_contract.get(key)
            for key in (
                "style_tag",
                "motif",
                "required_visual_keywords",
                "forbidden_visual_tokens",
                "asset_strategy_mode",
                "asset_provider",
                "external_image_generation",
                "asset_variant_count",
                "asset_detail_tier",
            )
        }

    production_result = build_production_artifact(
        state=state,
        deps=deps,
        gdd=gdd,
        design_spec=design_spec,
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        core_loop_type=core_loop_type,
        asset_pack=asset_pack,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
    )
    build_artifact = production_result.build_artifact

    state["outputs"]["build_artifact"] = build_artifact.model_dump()
    state["outputs"]["game_slug"] = build_artifact.game_slug
    state["outputs"]["game_name"] = build_artifact.game_name
    state["outputs"]["game_genre"] = build_artifact.game_genre
    state["outputs"]["genre_engine"] = core_loop_type
    state["outputs"]["asset_pack"] = asset_pack["name"]
    state["outputs"]["artifact_path"] = build_artifact.artifact_path
    state["outputs"]["entrypoint_path"] = build_artifact.entrypoint_path
    state["outputs"]["artifact_html"] = build_artifact.artifact_html
    state["outputs"]["artifact_files"] = [row.model_dump() for row in build_artifact.artifact_files or []]
    state["outputs"]["artifact_manifest"] = build_artifact.artifact_manifest or {}
    runtime_guard = production_result.metadata.get("runtime_guard")
    if isinstance(runtime_guard, dict):
        state["outputs"]["builder_runtime_guard"] = runtime_guard

    selected_generation_meta = production_result.selected_generation_meta
    return append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.BUILDER,
        message=f"Production V2 artifact selected and polished (iteration={state['build_iteration']}).",
        metadata={
            "artifact": state["outputs"]["artifact_path"],
            "genre": genre,
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
            "generation_source": selected_generation_meta.get("generation_source", "stub"),
            **{
                key: value
                for key, value in selected_generation_meta.items()
                if key in {"model", "latency_ms", "reason", "vertex_error"}
            },
            **production_result.metadata,
        },
    )
