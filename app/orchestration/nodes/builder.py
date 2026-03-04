from __future__ import annotations

from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.builder_parts.asset_memory import collect_asset_memory_context, empty_asset_memory_context
from app.orchestration.nodes.builder_parts.assets import _build_hybrid_asset_bank, _resolve_asset_pack
from app.orchestration.nodes.builder_parts.bundle import _extract_hybrid_bundle_from_inline_html
from app.orchestration.nodes.builder_parts.html_runtime import _build_hybrid_engine_html
from app.orchestration.nodes.builder_parts.mode import (
    _build_generated_genre_directive,
    _build_request_capability_hint,
    _detect_unsupported_scope,
    _infer_core_loop_profile,
    _infer_core_loop_type,
    _is_safe_slug,
    _resolve_runtime_engine_mode,
    _synthesize_genre_profile,
    _slugify,
)
from app.orchestration.nodes.builder_parts.intent_contract import build_intent_contract, compute_intent_contract_hash
from app.orchestration.nodes.builder_parts.production_pipeline import build_production_artifact
from app.orchestration.nodes.builder_parts.synapse_contract import (
    build_synapse_contract,
    compute_synapse_contract_hash,
    validate_synapse_contract,
)
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import (
    AnalyzeContractPayload,
    DesignContractPayload,
    DesignSpecPayload,
    GDDPayload,
    PlanContractPayload,
)
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus

__all__ = [
    "run",
    "_build_hybrid_asset_bank",
    "_resolve_asset_pack",
    "_extract_hybrid_bundle_from_inline_html",
    "_build_hybrid_engine_html",
    "_build_generated_genre_directive",
    "_build_request_capability_hint",
    "_infer_core_loop_profile",
    "_infer_core_loop_type",
    "_resolve_runtime_engine_mode",
    "_synthesize_genre_profile",
]


def _contract_issue(label: str, issue: str) -> str:
    return f"{label}:{issue}"


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    return any(token in lowered for token in tokens)


def _merge_unique(base: list[str], additions: list[str], *, limit: int) -> list[str]:
    merged: list[str] = []
    for item in [*base, *additions]:
        text = str(item).strip()
        if text and text not in merged:
            merged.append(text)
        if len(merged) >= limit:
            break
    return merged


def _expand_prompt_contracts(
    *,
    keyword: str,
    title: str,
    genre: str,
    analyze_contract: AnalyzeContractPayload,
    plan_contract: PlanContractPayload,
    design_contract: DesignContractPayload,
) -> tuple[AnalyzeContractPayload, PlanContractPayload, DesignContractPayload]:
    haystack = " ".join([keyword, title, genre]).casefold()
    render_stack = "three.js"
    if _contains_any(haystack, ("2d", "pixel", "도트", "플랫", "카드게임", "보드게임")):
        render_stack = "phaser.js"

    analyze_scope_additions = [
        "single html artifact export",
        f"{render_stack} runtime enforcement",
        "builder selfcheck hard-gate",
    ]
    analyze_constraints_additions = [
        "framework enforcement: 3d->three.js / 2d->phaser.js",
        "single html output with embedded runtime compatibility",
        "no generic fallback route",
    ]
    analyze_forbidden_additions = [
        "request_faithful_generic fallback",
        "framework mismatch runtime output",
        "duplicate controls guidance",
    ]
    expanded_analyze = analyze_contract.model_copy(
        update={
            "intent": f"{keyword} 요청을 상세 스펙 계약으로 확장하고 고품질 런타임으로 제작",
            "scope_in": _merge_unique(analyze_contract.scope_in, analyze_scope_additions, limit=10),
            "hard_constraints": _merge_unique(analyze_contract.hard_constraints, analyze_constraints_additions, limit=10),
            "forbidden_patterns": _merge_unique(analyze_contract.forbidden_patterns, analyze_forbidden_additions, limit=12),
            "success_outcome": f"요청({keyword})이 축약 없이 확장되어 {render_stack} 기반 단일 아티팩트로 실행된다.",
        }
    )

    mechanics_additions = ["core movement", "primary action loop", "clear fail-state and recovery"]
    progression_additions = ["onboarding loop", "mid escalation loop", "late mastery loop"]
    encounter_additions = ["baseline pressure", "variant encounter pattern", "high-intensity checkpoint"]
    risk_additions = ["safe scoring route", "high-risk high-reward route", "recover route after failure"]
    control_model = f"{genre} / {render_stack} / keyboard-first deterministic loop"

    if _contains_any(haystack, ("race", "racing", "레이싱", "드리프트", "f1", "formula")):
        mechanics_additions = ["analog steering", "speed control + boost timing", "checkpoint racing loop"]
        progression_additions = ["starter lap", "mid lap pressure", "late lap optimization"]
        encounter_additions = ["traffic hazard", "curve challenge", "overtake window"]
        risk_additions = ["safe line", "aggressive overtake line", "recovery braking line"]
    elif _contains_any(haystack, ("flight", "비행", "pilot", "aircraft", "조종")):
        mechanics_additions = ["pitch-roll-yaw control", "throttle stability management", "waypoint chaining"]
        progression_additions = ["air-control onboarding", "mid-air hazard pressure", "precision finale"]
        encounter_additions = ["ring gate", "hazard corridor", "stability check segment"]
        risk_additions = ["safe vector", "high-speed route", "recovery vector"]
    elif _contains_any(haystack, ("fps", "shooter", "사격", "슈팅", "총")):
        mechanics_additions = ["aim + movement loop", "attack cooldown rhythm", "positioning counterplay"]
        progression_additions = ["threat introduction", "pattern escalation", "survival burst"]
        encounter_additions = ["light enemy", "heavy enemy", "mixed pressure wave"]
        risk_additions = ["cover route", "aggressive route", "retreat and reset route"]
    elif _contains_any(haystack, ("fight", "fighting", "격투", "brawler", "근접")):
        mechanics_additions = ["spacing loop", "combo timing", "dodge-counter rhythm"]
        progression_additions = ["footsies onboarding", "pressure exchange", "combo mastery"]
        encounter_additions = ["jab-heavy mix", "counter window", "clutch duel phase"]
        risk_additions = ["safe poke", "commit combo", "reset neutral"]

    expanded_plan = plan_contract.model_copy(
        update={
            "core_mechanics": _merge_unique(plan_contract.core_mechanics, mechanics_additions, limit=12),
            "progression_plan": _merge_unique(plan_contract.progression_plan, progression_additions, limit=12),
            "encounter_plan": _merge_unique(plan_contract.encounter_plan, encounter_additions, limit=12),
            "risk_reward_plan": _merge_unique(plan_contract.risk_reward_plan, risk_additions, limit=12),
            "control_model": control_model,
        }
    )

    design_camera_additions = ["camera readability preserved at all times", "hud remains concise and non-overlapping"]
    design_asset_additions = ["player silhouette set", "enemy silhouette set", "interactive object set", "environment prop set"]
    design_layers_additions = ["foreground gameplay layer", "midground interaction layer", "animated background layer", "feedback fx layer"]
    design_fx_additions = ["hit feedback pulse", "damage feedback pulse", "objective progress feedback"]
    design_readability_additions = ["player/enemy contrast", "critical object highlight", "no overflow clipping"]

    expanded_design = design_contract.model_copy(
        update={
            "camera_ui_contract": _merge_unique(design_contract.camera_ui_contract, design_camera_additions, limit=12),
            "asset_blueprint_2d3d": _merge_unique(design_contract.asset_blueprint_2d3d, design_asset_additions, limit=18),
            "scene_layers": _merge_unique(design_contract.scene_layers, design_layers_additions, limit=12),
            "feedback_fx_contract": _merge_unique(design_contract.feedback_fx_contract, design_fx_additions, limit=12),
            "readability_contract": _merge_unique(design_contract.readability_contract, design_readability_additions, limit=12),
        }
    )

    return expanded_analyze, expanded_plan, expanded_design


def _normalize_core_loop_type(core_loop_type: str) -> str:
    lowered = str(core_loop_type).strip().casefold()
    if lowered == "request_faithful_generic":
        return "comic_action_brawler_3d"
    return str(core_loop_type).strip() or "comic_action_brawler_3d"


def _require_contract_payload(raw: object, model_cls):
    if not isinstance(raw, dict):
        raise ValueError(f"{model_cls.__name__}_missing")
    return model_cls.model_validate(raw)


def _validate_prebuild_contracts(
    *,
    analyze_contract: AnalyzeContractPayload,
    plan_contract: PlanContractPayload,
    design_contract: DesignContractPayload,
) -> list[str]:
    issues: list[str] = []
    if len(analyze_contract.scope_in) < 2:
        issues.append(_contract_issue("analyze_contract", "scope_in_underfilled"))
    if len(plan_contract.core_mechanics) < 2:
        issues.append(_contract_issue("plan_contract", "core_mechanics_underfilled"))
    if len(plan_contract.progression_plan) < 2:
        issues.append(_contract_issue("plan_contract", "progression_plan_underfilled"))
    if len(plan_contract.balance_baseline) < 2:
        issues.append(_contract_issue("plan_contract", "balance_baseline_underfilled"))
    if len(design_contract.asset_blueprint_2d3d) < 3:
        issues.append(_contract_issue("design_contract", "asset_blueprint_underfilled"))
    if len(design_contract.scene_layers) < 2:
        issues.append(_contract_issue("design_contract", "scene_layers_underfilled"))
    return issues


def _validate_intent_contract(intent_contract) -> list[str]:
    issues: list[str] = []
    if not str(intent_contract.fantasy).strip():
        issues.append("fantasy_missing")
    if not intent_contract.player_verbs:
        issues.append("player_verbs_missing")
    if not str(intent_contract.camera_interaction).strip():
        issues.append("camera_interaction_missing")
    if not intent_contract.progression_loop:
        issues.append("progression_loop_missing")
    if not str(intent_contract.fail_restart_loop).strip():
        issues.append("fail_restart_loop_missing")
    if not intent_contract.non_negotiables:
        issues.append("non_negotiables_missing")
    return issues


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.BUILD,
        agent_name=PipelineAgentName.DEVELOPER,
    )
    if gated_state is not None:
        return gated_state

    state["build_iteration"] += 1

    try:
        gdd = _require_contract_payload(state["outputs"].get("gdd"), GDDPayload)
        design_spec = _require_contract_payload(state["outputs"].get("design_spec"), DesignSpecPayload)
    except (ValidationError, ValueError) as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "upstream_contract_missing_or_invalid"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: GDD 또는 Design spec 계약이 누락되었거나 형식이 올바르지 않습니다.",
            reason=state["reason"],
            metadata={
                "strict_vertex_only": bool(getattr(deps.vertex_service.settings, "strict_vertex_only", True)),
                "contract_status": "fail",
                "contract_error": str(exc),
                "deliverables": ["prebuild_contract_validator"],
            },
        )

    title = gdd.title
    genre = gdd.genre
    settings = deps.vertex_service.settings
    strict_vertex_only = bool(getattr(settings, "strict_vertex_only", True))
    try:
        analyze_contract = _require_contract_payload(state["outputs"].get("analyze_contract"), AnalyzeContractPayload)
        plan_contract = _require_contract_payload(state["outputs"].get("plan_contract"), PlanContractPayload)
        design_contract = _require_contract_payload(state["outputs"].get("design_contract"), DesignContractPayload)
    except (ValidationError, ValueError) as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "upstream_contract_missing_or_invalid"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 업스트림 계약이 누락되었거나 형식이 올바르지 않습니다.",
            reason=state["reason"],
            metadata={
                "strict_vertex_only": strict_vertex_only,
                "contract_status": "fail",
                "contract_error": str(exc),
                "deliverables": ["prebuild_contract_validator"],
            },
        )
    if strict_vertex_only:
        source_rows = {
            "analyze_contract_source": str(state["outputs"].get("analyze_contract_source", "")).strip().casefold(),
            "gdd_source": str(state["outputs"].get("gdd_source", "")).strip().casefold(),
            "plan_contract_source": str(state["outputs"].get("plan_contract_source", "")).strip().casefold(),
            "design_spec_source": str(state["outputs"].get("design_spec_source", "")).strip().casefold(),
            "design_contract_source": str(state["outputs"].get("design_contract_source", "")).strip().casefold(),
        }
        violated = [key for key, source in source_rows.items() if source != "vertex"]
        if violated:
            state["status"] = PipelineStatus.ERROR
            state["reason"] = "upstream_contract_source_untrusted"
            return append_log(
                state,
                stage=PipelineStage.BUILD,
                status=PipelineStatus.ERROR,
                agent_name=PipelineAgentName.DEVELOPER,
                message="빌드 중단: Vertex source 계약이 충족되지 않았습니다.",
                reason=state["reason"],
                metadata={
                    "strict_vertex_only": strict_vertex_only,
                    "violated_sources": violated,
                    "source_rows": source_rows,
                    "contract_status": "fail",
                    "deliverables": ["prebuild_contract_validator"],
                },
            )
    analyze_contract, plan_contract, design_contract = _expand_prompt_contracts(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        analyze_contract=analyze_contract,
        plan_contract=plan_contract,
        design_contract=design_contract,
    )
    state["outputs"]["analyze_contract"] = analyze_contract.model_dump()
    state["outputs"]["plan_contract"] = plan_contract.model_dump()
    state["outputs"]["design_contract"] = design_contract.model_dump()
    contract_issues = _validate_prebuild_contracts(
        analyze_contract=analyze_contract,
        plan_contract=plan_contract,
        design_contract=design_contract,
    )
    if contract_issues:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "builder_contract_validation_failed"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 업스트림 계약 검증 실패.",
            reason=state["reason"],
            metadata={
                "contract_issues": contract_issues,
                "contract_status": "fail",
                "deliverables": ["prebuild_contract_validator"],
                "contribution_score": 1.2,
                "contract_enforcement": "strict",
                "strict_vertex_only": strict_vertex_only,
            },
        )

    safe_slug = state["outputs"].get("safe_slug")
    if isinstance(safe_slug, str) and safe_slug and _is_safe_slug(safe_slug):
        slug = safe_slug
    else:
        slug = _slugify(state["keyword"])

    palette = design_spec.palette
    accent_color = str(palette[0]) if palette else "#22C55E"
    core_loop_profile = _infer_core_loop_profile(keyword=state["keyword"], title=title, genre=genre)
    core_loop_type = _normalize_core_loop_type(
        str(core_loop_profile.get("core_loop_type", _infer_core_loop_type(keyword=state["keyword"], title=title, genre=genre)))
    )
    runtime_engine_mode = _resolve_runtime_engine_mode(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        core_loop_type=core_loop_type,
    )
    state["outputs"]["runtime_engine_mode"] = runtime_engine_mode
    request_capability_hint = _build_request_capability_hint(keyword=state["keyword"], title=title, genre=genre)
    generated_genre_profile = _synthesize_genre_profile(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        core_loop_profile=core_loop_profile,
    )
    generated_genre_directive = _build_generated_genre_directive(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        genre_profile=generated_genre_profile,
    )
    try:
        intent_contract = build_intent_contract(
            keyword=state["keyword"],
            title=title,
            gdd=gdd,
            analyze_contract=analyze_contract,
            plan_contract=plan_contract,
            design_contract=design_contract,
        )
    except ValidationError as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "intent_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 의도 계약 생성이 스키마 검증을 통과하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "validation_error": str(exc),
                "contract_status": "fail",
                "deliverables": ["intent_contract_validator"],
                "contribution_score": 1.2,
                "strict_vertex_only": strict_vertex_only,
            },
        )
    intent_issues = _validate_intent_contract(intent_contract)
    if intent_issues:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "intent_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 의도 계약 필수 항목이 충족되지 않았습니다.",
            reason=state["reason"],
            metadata={
                "intent_issues": intent_issues,
                "contract_status": "fail",
                "deliverables": ["intent_contract_validator"],
                "contribution_score": 1.3,
                "strict_vertex_only": strict_vertex_only,
            },
        )
    intent_contract_hash = compute_intent_contract_hash(intent_contract)
    state["outputs"]["intent_contract"] = intent_contract.model_dump()
    state["outputs"]["intent_contract_hash"] = intent_contract_hash

    synapse_contract = build_synapse_contract(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        objective=gdd.objective,
        analyze_contract=analyze_contract.model_dump(),
        plan_contract=plan_contract.model_dump(),
        design_contract=design_contract.model_dump(),
        design_spec=design_spec.model_dump(),
        base_contract={
            "quality_bar": {
                "quality_min": int(getattr(settings, "qa_min_quality_score", 50)),
                "gameplay_min": int(getattr(settings, "qa_min_gameplay_score", 55)),
                "visual_min": int(getattr(settings, "qa_min_visual_score", 45)),
            }
        },
    )
    synapse_issues = validate_synapse_contract(synapse_contract)
    if synapse_issues:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "synapse_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 시냅스 계약 필수 항목이 충족되지 않았습니다.",
            reason=state["reason"],
            metadata={
                "synapse_issues": synapse_issues,
                "contract_status": "fail",
                "deliverables": ["synapse_contract_validator"],
                "contribution_score": 1.3,
                "strict_vertex_only": strict_vertex_only,
            },
        )
    synapse_contract_hash = compute_synapse_contract_hash(synapse_contract)
    state["outputs"]["synapse_contract"] = synapse_contract
    state["outputs"]["synapse_contract_hash"] = synapse_contract_hash
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
            agent_name=PipelineAgentName.DEVELOPER,
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
                ],
            },
        )

    asset_pack = _resolve_asset_pack(core_loop_type=core_loop_type, palette=palette)
    if deps.vertex_service.settings.builder_asset_memory_enabled:
        asset_memory_context = collect_asset_memory_context(
            state=state,
            deps=deps,
            core_loop_type=core_loop_type,
        )
    else:
        asset_memory_context = empty_asset_memory_context()
    state["outputs"]["asset_memory_context"] = asset_memory_context.registry_snapshot

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.DEVELOPER,
        message="Asset memory retriever composed prior successes/failures.",
        metadata={
            "core_loop_type": core_loop_type,
            "runtime_engine_mode": runtime_engine_mode,
            "core_loop_profile": core_loop_profile,
            "request_capability_hint_applied": bool(request_capability_hint),
            "generated_genre_profile": generated_genre_profile,
            "generated_genre_directive_applied": bool(generated_genre_directive),
            "intent_contract_hash": intent_contract_hash,
            "synapse_contract_hash": synapse_contract_hash,
            "asset_memory_hint_applied": bool(asset_memory_context.hint),
            "asset_memory_profile": asset_memory_context.retrieval_profile,
            "asset_memory_snapshot": asset_memory_context.registry_snapshot,
            "deliverables": ["asset_memory_context", "asset_bank_profile"],
            "contract_status": "pass" if not contract_issues else "warn",
            "contribution_score": 3.7,
        },
    )

    art_direction_contract = state["outputs"].get("art_direction_contract")
    if not isinstance(art_direction_contract, dict):
        art_direction_contract = {}

    asset_bank_files, runtime_asset_manifest = _build_hybrid_asset_bank(
        slug=slug,
        core_loop_type=core_loop_type,
        asset_pack=asset_pack,
        art_direction_contract=art_direction_contract,
        retrieval_profile=asset_memory_context.retrieval_profile,
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
        runtime_engine_mode=runtime_engine_mode,
        asset_pack=asset_pack,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
        memory_hint=asset_memory_context.hint,
        memory_tokens=asset_memory_context.recurring_failures,
        request_capability_hint=request_capability_hint,
        generated_genre_directive=generated_genre_directive,
        intent_contract=intent_contract.model_dump(),
        synapse_contract=synapse_contract,
    )
    playability_hard_gate = bool(getattr(deps.vertex_service.settings, "builder_playability_hard_gate", True))
    playability_passed = bool(production_result.metadata.get("playability_passed", True))
    if playability_hard_gate and not playability_passed:
        fail_reasons = production_result.metadata.get("playability_fail_reasons", [])
        fail_tokens = [str(item).strip() for item in fail_reasons if str(item).strip()] if isinstance(fail_reasons, list) else []
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "builder_playability_unmet"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 플레이 가능성 하드게이트를 통과하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "playability_score": production_result.metadata.get("playability_score"),
                "playability_fail_reasons": fail_tokens,
                "playability_refinement_rounds_executed": production_result.metadata.get("playability_refinement_rounds_executed"),
                "deliverables": ["playability_gate", "builder_refinement_report"],
                "contract_status": "fail",
                "contribution_score": 1.6,
                **production_result.metadata,
            },
        )
    quality_floor_enforced = bool(production_result.metadata.get("quality_floor_enforced", False))
    quality_floor_passed = bool(production_result.metadata.get("quality_floor_passed", True))
    if quality_floor_enforced and not quality_floor_passed:
        fail_reasons = production_result.metadata.get("quality_floor_fail_reasons", [])
        fail_tokens = [str(item).strip() for item in fail_reasons if str(item).strip()] if isinstance(fail_reasons, list) else []
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "builder_quality_floor_unmet"
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.DEVELOPER,
            message="빌드 중단: 자동 품질 하한선을 통과하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "quality_floor_score": production_result.metadata.get("quality_floor_score"),
                "quality_floor_fail_reasons": fail_tokens,
                "final_builder_quality_score": production_result.metadata.get("final_builder_quality_score"),
                "final_placeholder_heavy": production_result.metadata.get("final_placeholder_heavy"),
                "deliverables": ["quality_floor_gate", "builder_refinement_report"],
                "contract_status": "fail",
                "contribution_score": 1.8,
                **production_result.metadata,
            },
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
    state["outputs"]["playability_score"] = production_result.metadata.get("playability_score")
    state["outputs"]["playability_fail_reasons"] = production_result.metadata.get("playability_fail_reasons", [])
    state["outputs"]["substrate_id"] = production_result.metadata.get("substrate_id")
    state["outputs"]["camera_model"] = production_result.metadata.get("camera_model")
    state["outputs"]["capability_profile"] = production_result.metadata.get("capability_profile")
    state["outputs"]["module_plan"] = production_result.metadata.get("module_plan")
    state["outputs"]["selfcheck_result"] = production_result.metadata.get("selfcheck_result")
    state["outputs"]["rqc_passed"] = production_result.metadata.get("rqc_passed")
    state["outputs"]["module_signature"] = production_result.metadata.get("module_signature")
    state["outputs"]["rebuild_source"] = production_result.metadata.get("rebuild_source")
    runtime_guard = production_result.metadata.get("runtime_guard")
    if isinstance(runtime_guard, dict):
        state["outputs"]["builder_runtime_guard"] = runtime_guard

    try:
        capability_profile = production_result.metadata.get("capability_profile")
        if isinstance(capability_profile, dict):
            deps.repository.upsert_capability_profile_entry(
                {
                    "pipeline_id": str(state["pipeline_id"]),
                    "game_slug": slug,
                    "keyword": state["keyword"],
                    "core_loop_type": core_loop_type,
                    "profile_id": str(capability_profile.get("profile_id", "")).strip() or f"cp-{slug}",
                    "capability_profile": capability_profile,
                    "module_plan": production_result.metadata.get("module_plan")
                    if isinstance(production_result.metadata.get("module_plan"), dict)
                    else {},
                    "module_signature": str(production_result.metadata.get("module_signature", "")) or None,
                }
            )
        runtime_modules = production_result.metadata.get("runtime_modules")
        if isinstance(runtime_modules, list):
            for module_row in runtime_modules:
                if not isinstance(module_row, dict):
                    continue
                module_id = str(module_row.get("module_id", "")).strip()
                if not module_id:
                    continue
                deps.repository.upsert_runtime_module_registry_entry(
                    {
                        "module_id": module_id,
                        "capability_tags": module_row.get("capability_tags") if isinstance(module_row.get("capability_tags"), list) else [],
                        "version": str(module_row.get("version", "1.0.0")).strip() or "1.0.0",
                        "stability_score": float(module_row.get("stability_score", 0) or 0),
                        "metadata": {
                            "layer": module_row.get("layer"),
                            "description": module_row.get("description"),
                        },
                    }
                )
        selfcheck_result = production_result.metadata.get("selfcheck_result")
        if isinstance(selfcheck_result, dict):
            deps.repository.insert_builder_contract_report(
                {
                    "pipeline_id": str(state["pipeline_id"]),
                    "rqc_version": str(production_result.metadata.get("rqc_version", "rqc-1")),
                    "checks": selfcheck_result.get("checks") if isinstance(selfcheck_result.get("checks"), dict) else {},
                    "failed_reasons": selfcheck_result.get("failed_reasons")
                    if isinstance(selfcheck_result.get("failed_reasons"), list)
                    else [],
                    "module_signature": str(production_result.metadata.get("module_signature", "")).strip() or "unknown",
                    "score": int(selfcheck_result.get("score", 0) or 0),
                }
            )
    except Exception:
        # repository side persistence is best-effort and must not block build completion.
        pass

    selected_generation_meta = production_result.selected_generation_meta
    return append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.DEVELOPER,
        message=f"Production V2 artifact selected and polished (iteration={state['build_iteration']}).",
        metadata={
            "artifact": state["outputs"]["artifact_path"],
            "game_slug": slug,
            "genre": genre,
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
            "generation_source": selected_generation_meta.get("generation_source", "stub"),
            **{
                key: value
                for key, value in selected_generation_meta.items()
                if key
                in {
                    "model",
                    "latency_ms",
                    "reason",
                    "vertex_error",
                    "model_name",
                    "max_output_tokens",
                    "prompt_contract_version",
                    "usage",
                }
            },
            "deliverables": [
                "build_artifact",
                "artifact_manifest",
                "runtime_guard",
                "candidate_scoreboard",
            ],
            "contract_status": "pass",
            "contract_summary": "upstream contracts consumed for assembly build",
            "contribution_score": 4.6,
            "contract_issues": contract_issues,
            "generated_genre_profile": generated_genre_profile,
            "generated_genre_directive_applied": bool(generated_genre_directive),
            **production_result.metadata,
        },
    )
