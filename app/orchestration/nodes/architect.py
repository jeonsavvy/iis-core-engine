from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate, classify_vertex_unavailable_reason
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import AnalyzeContractPayload, GDDPayload, PlanContractPayload
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


def _dedupe_rows(rows: list[str], *, limit: int) -> list[str]:
    deduped: list[str] = []
    for row in rows:
        text = str(row).strip()
        if text and text not in deduped:
            deduped.append(text)
        if len(deduped) >= limit:
            break
    return deduped


def _contains_any(haystack: str, tokens: tuple[str, ...]) -> bool:
    lowered = haystack.casefold()
    return any(token in lowered for token in tokens)


def _build_dual_agent_plan_bundle(
    *,
    keyword: str,
    analyze_contract: AnalyzeContractPayload,
) -> tuple[GDDPayload, dict[str, object], PlanContractPayload]:
    hint = " ".join(
        [
            keyword,
            analyze_contract.intent,
            " ".join(analyze_contract.scope_in),
            " ".join(analyze_contract.hard_constraints),
        ]
    ).casefold()
    is_2d = _contains_any(hint, ("2d", "pixel", "도트", "탑다운", "퍼즐", "보드", "카드"))
    is_racing = _contains_any(hint, ("racing", "race", "레이싱", "서킷", "f1", "formula", "drift"))
    is_flight = _contains_any(hint, ("flight", "pilot", "air", "비행", "조종", "cockpit"))
    is_shooter = _contains_any(hint, ("shooter", "shoot", "fps", "총", "사격", "슈팅"))
    is_brawler = _contains_any(hint, ("brawler", "fight", "fighting", "격투", "근접", "콤보"))

    genre = "action_3d"
    visual_style = "cinematic-neon"
    objective = f"{keyword} 요청을 의도 손실 없이 실행 가능한 웹게임으로 완성"
    core_mechanics = ["movement", "primary action", "risk-reward loop"]
    progression_plan = ["0-45s onboarding", "45-90s escalation", "90-180s mastery pressure"]
    encounter_plan = ["baseline challenge", "variant challenge", "climax challenge"]
    risk_reward_plan = ["safe route", "aggressive route", "recovery route"]
    control_model = "keyboard + pointer deterministic loop"
    balance_baseline = {"base_hp": 100.0, "spawn_rate": 1.0, "difficulty_scale": 1.0}

    if is_2d:
        genre = "arcade_2d"
        visual_style = "stylized-2d"
        core_mechanics = ["move", "jump_or_dash", "collect_or_attack"]
        control_model = "phaser 2d keyboard loop"
    elif is_racing:
        genre = "racing_3d"
        visual_style = "formula-cinematic"
        objective = f"{keyword} 요청의 레이싱 감성과 속도감을 유지하며 랩 루프를 완성"
        core_mechanics = ["steer", "throttle", "brake", "boost", "checkpoint"]
        progression_plan = ["lap onboarding", "mid-lap pressure", "late-lap optimization"]
        encounter_plan = ["traffic hazard", "curve pressure", "overtake window"]
        risk_reward_plan = ["safe line", "aggressive overtake", "recovery braking line"]
        control_model = "three.js vehicle steering + throttle loop"
        balance_baseline = {"base_hp": 100.0, "spawn_rate": 1.2, "difficulty_scale": 1.15}
    elif is_flight:
        genre = "flight_sim_3d"
        visual_style = "aero-cinematic"
        objective = f"{keyword} 요청의 비행 판타지와 자유 이동 체감을 유지하며 경유 루프를 완성"
        core_mechanics = ["pitch_roll_yaw", "throttle control", "waypoint chaining", "boost window"]
        progression_plan = ["air-control onboarding", "hazard corridor", "precision finale"]
        encounter_plan = ["ring gate", "terrain hazard", "stability challenge"]
        risk_reward_plan = ["safe vector", "high-speed route", "recovery vector"]
        control_model = "three.js flight control loop"
        balance_baseline = {"base_hp": 100.0, "spawn_rate": 1.0, "difficulty_scale": 1.12}
    elif is_shooter:
        genre = "shooter_3d"
        visual_style = "combat-neon"
        core_mechanics = ["move", "aim", "shoot", "reload_or_cooldown", "evade"]
        progression_plan = ["threat intro", "pattern escalation", "survival burst"]
        encounter_plan = ["light enemy", "heavy enemy", "mixed wave"]
        risk_reward_plan = ["cover route", "aggressive push", "fallback reset"]
        control_model = "three.js shooter loop"
        balance_baseline = {"base_hp": 100.0, "spawn_rate": 1.1, "difficulty_scale": 1.2}
    elif is_brawler:
        genre = "brawler_3d"
        visual_style = "impact-comic"
        core_mechanics = ["spacing", "combo timing", "dodge counter", "finisher"]
        progression_plan = ["footsies onboarding", "pressure exchange", "combo mastery"]
        encounter_plan = ["jab-heavy mix", "counter window", "clutch duel"]
        risk_reward_plan = ["safe poke", "commit combo", "neutral reset"]
        control_model = "three.js melee brawler loop"
        balance_baseline = {"base_hp": 120.0, "spawn_rate": 0.9, "difficulty_scale": 1.14}

    base_title = keyword.strip()[:70] or "IIS Arcade"
    gdd = GDDPayload(
        title=base_title,
        genre=genre,
        objective=objective[:300],
        visual_style=visual_style,
    )
    references = _dedupe_rows(
        [
            f"{keyword} core loop reference",
            f"{genre} pacing baseline",
            f"{visual_style} readability baseline",
            *analyze_contract.scope_in[:4],
        ],
        limit=8,
    )
    research_summary: dict[str, object] = {
        "intent": analyze_contract.intent,
        "references": references,
    }
    plan_contract = PlanContractPayload(
        core_mechanics=_dedupe_rows(core_mechanics + analyze_contract.scope_in[:3], limit=12),
        progression_plan=_dedupe_rows(progression_plan, limit=12),
        encounter_plan=_dedupe_rows(encounter_plan, limit=12),
        risk_reward_plan=_dedupe_rows(risk_reward_plan, limit=12),
        control_model=control_model[:120],
        balance_baseline=balance_baseline,
    )
    return gdd, research_summary, plan_contract


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.PLAN,
        agent_name=PipelineAgentName.PLANNER,
    )
    if gated_state is not None:
        return gated_state

    resume_stage = str(state["outputs"].get("resume_stage", "")).strip().casefold()
    if resume_stage in {"design", "build", "qa_runtime", "qa_quality", "release", "report"}:
        cached_gdd = state["outputs"].get("gdd")
        cached_plan = state["outputs"].get("plan_contract")
        if isinstance(cached_gdd, dict) and cached_gdd and isinstance(cached_plan, dict) and cached_plan:
            state["status"] = PipelineStatus.RUNNING
            return append_log(
                state,
                stage=PipelineStage.PLAN,
                status=PipelineStatus.SUCCESS,
                agent_name=PipelineAgentName.PLANNER,
                message="기획 재개: 기존 GDD/plan contract를 재사용합니다.",
                metadata={
                    "resume_stage": resume_stage,
                    "reused_cached_contract": True,
                    "contract_status": "pass",
                },
            )

    keyword = state["keyword"]
    settings = deps.vertex_service.settings
    strict_vertex_only = bool(getattr(settings, "strict_vertex_only", True))
    dual_agent_mode = bool(getattr(settings, "pipeline_dual_agent_mode", False))
    shared_contract = state["outputs"].get("shared_generation_contract")
    typed_shared_contract = shared_contract if isinstance(shared_contract, dict) else None
    shared_contract_issues = validate_shared_generation_contract(typed_shared_contract)
    if shared_contract_issues:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "shared_generation_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PLANNER,
            message="기획 중단: 공유 생성 계약이 유효하지 않습니다.",
            reason=state["reason"],
            metadata={
                "shared_generation_contract_issues": shared_contract_issues,
                "contract_status": "fail",
                "deliverables": ["shared_generation_contract_gate"],
            },
        )

    if dual_agent_mode:
        try:
            analyze_contract = AnalyzeContractPayload.model_validate(state["outputs"].get("analyze_contract", {}))
        except Exception as exc:
            state["status"] = PipelineStatus.ERROR
            state["reason"] = "analyze_contract_missing_for_dual_agent"
            return append_log(
                state,
                stage=PipelineStage.PLAN,
                status=PipelineStatus.ERROR,
                agent_name=PipelineAgentName.PLANNER,
                message="기획 중단: 2-agent 모드에서 analyze contract가 유효하지 않습니다.",
                reason=state["reason"],
                metadata={
                    "pipeline_dual_agent_mode": True,
                    "validation_error": _validation_error_detail(exc),
                    "contract_status": "fail",
                },
            )
        gdd, research_summary, plan_contract = _build_dual_agent_plan_bundle(
            keyword=keyword,
            analyze_contract=analyze_contract,
        )
        state["outputs"]["research_summary"] = research_summary
        state["outputs"]["gdd"] = gdd.model_dump()
        state["outputs"]["gdd_source"] = "dual_agent_synth"
        state["outputs"]["gdd_meta"] = {"generation_source": "dual_agent_synth", "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        state["outputs"]["plan_contract"] = plan_contract.model_dump()
        state["outputs"]["plan_contract_source"] = "dual_agent_synth"
        state["outputs"]["plan_contract_meta"] = {
            "generation_source": "dual_agent_synth",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        shared_contract = merge_shared_generation_contract(
            contract=typed_shared_contract,
            keyword=keyword,
            title=gdd.title,
            objective=gdd.objective,
            runtime_engine_mode=None,
        )
        shared_contract_hash = compute_shared_generation_contract_hash(shared_contract)
        state["outputs"]["shared_generation_contract"] = shared_contract
        state["outputs"]["shared_generation_contract_hash"] = shared_contract_hash
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=PipelineStatus.SUCCESS,
            agent_name=PipelineAgentName.PLANNER,
            message="2-agent 모드: 기획 계약을 로컬 합성으로 완료했습니다.",
            metadata={
                "pipeline_dual_agent_mode": True,
                "deliverables": [
                    "gdd.title/genre/objective",
                    "research_summary.references",
                    "plan_contract.core_mechanics",
                    "plan_contract.balance_baseline",
                ],
                "contract_status": "pass",
                "contract_summary": f"{len(plan_contract.core_mechanics)} mechanics / {len(plan_contract.progression_plan)} progression beats",
                "contribution_score": 4.1,
                "shared_generation_contract_hash": shared_contract_hash,
                "strict_vertex_only": strict_vertex_only,
                "gdd_source": "dual_agent_synth",
                "plan_source": "dual_agent_synth",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "model": "deterministic_contract_synthesizer",
            },
        )

    try:
        generated = deps.vertex_service.generate_gdd_bundle(keyword, shared_contract=typed_shared_contract)
    except TypeError:
        generated = deps.vertex_service.generate_gdd_bundle(keyword)
    gdd_source = str(generated.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and gdd_source != "vertex":
        reason, retryable = classify_vertex_unavailable_reason(
            default_reason="gdd_unavailable",
            generation_meta=generated.meta,
        )
        state["status"] = PipelineStatus.RETRY if retryable else PipelineStatus.ERROR
        state["reason"] = reason
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=state["status"],
            agent_name=PipelineAgentName.PLANNER,
            message="기획 지연: Vertex GDD를 확보하지 못했습니다."
            if retryable
            else "기획 중단: Vertex GDD를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "generation_source": gdd_source,
                "strict_vertex_only": strict_vertex_only,
                "retryable": retryable,
                "upstream_reason": str(generated.meta.get("reason", "")).strip() or None,
                "vertex_error": str(generated.meta.get("vertex_error", "")).strip() or None,
                "deliverables": ["gdd_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
        )
    payload = generated.payload
    try:
        gdd = GDDPayload.model_validate(payload.get("gdd", {}))
    except Exception as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "gdd_invalid"
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PLANNER,
            message="기획 중단: GDD payload 검증 실패.",
            reason=state["reason"],
            metadata={
                "generation_source": gdd_source,
                "strict_vertex_only": strict_vertex_only,
                "validation_error": _validation_error_detail(exc),
                "deliverables": ["gdd_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
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
    state["outputs"]["gdd_source"] = gdd_source
    state["outputs"]["gdd_meta"] = dict(generated.meta)
    try:
        generated_contract = deps.vertex_service.generate_plan_contract(
            keyword=keyword,
            gdd=gdd.model_dump(),
            research_summary=research_summary,
            shared_contract=typed_shared_contract,
        )
    except TypeError:
        generated_contract = deps.vertex_service.generate_plan_contract(
            keyword=keyword,
            gdd=gdd.model_dump(),
            research_summary=research_summary,
        )
    plan_source = str(generated_contract.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and plan_source != "vertex":
        reason, retryable = classify_vertex_unavailable_reason(
            default_reason="plan_contract_unavailable",
            generation_meta=generated_contract.meta,
        )
        state["status"] = PipelineStatus.RETRY if retryable else PipelineStatus.ERROR
        state["reason"] = reason
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=state["status"],
            agent_name=PipelineAgentName.PLANNER,
            message="기획 지연: Vertex plan contract를 확보하지 못했습니다."
            if retryable
            else "기획 중단: Vertex plan contract를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "gdd_source": gdd_source,
                "plan_source": plan_source,
                "strict_vertex_only": strict_vertex_only,
                "retryable": retryable,
                "upstream_reason": str(generated_contract.meta.get("reason", "")).strip() or None,
                "vertex_error": str(generated_contract.meta.get("vertex_error", "")).strip() or None,
                "deliverables": ["plan_contract_gate"],
                "contract_status": "fail",
                **generated_contract.meta,
            },
        )
    try:
        plan_contract = PlanContractPayload.model_validate(generated_contract.payload)
    except Exception as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "plan_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PLANNER,
            message="기획 중단: plan contract payload 검증 실패.",
            reason=state["reason"],
            metadata={
                "gdd_source": gdd_source,
                "plan_source": plan_source,
                "strict_vertex_only": strict_vertex_only,
                "validation_error": _validation_error_detail(exc),
                "deliverables": ["plan_contract_gate"],
                "contract_status": "fail",
                **generated_contract.meta,
            },
        )
    state["outputs"]["plan_contract"] = plan_contract.model_dump()
    state["outputs"]["plan_contract_source"] = plan_source
    state["outputs"]["plan_contract_meta"] = dict(generated_contract.meta)
    shared_contract = merge_shared_generation_contract(
        contract=typed_shared_contract,
        keyword=keyword,
        title=gdd.title,
        objective=gdd.objective,
        runtime_engine_mode=None,
    )
    shared_contract_hash = compute_shared_generation_contract_hash(shared_contract)
    state["outputs"]["shared_generation_contract"] = shared_contract
    state["outputs"]["shared_generation_contract_hash"] = shared_contract_hash
    gdd_usage = generated.meta.get("usage", {}) if isinstance(generated.meta.get("usage", {}), dict) else {}
    plan_usage = generated_contract.meta.get("usage", {}) if isinstance(generated_contract.meta.get("usage", {}), dict) else {}
    usage = {
        "prompt_tokens": int(gdd_usage.get("prompt_tokens", 0) or 0) + int(plan_usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(gdd_usage.get("completion_tokens", 0) or 0) + int(plan_usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(gdd_usage.get("total_tokens", 0) or 0) + int(plan_usage.get("total_tokens", 0) or 0),
    }
    references_value = research_summary.get("references") if isinstance(research_summary, dict) else []
    reference_count = len(references_value) if isinstance(references_value, list) else 0
    meta = {
        "reference_count": reference_count,
        "deliverables": [
            "gdd.title/genre/objective",
            "research_summary.references",
            "plan_contract.core_mechanics",
            "plan_contract.balance_baseline",
        ],
        "contract_status": "pass",
        "contract_summary": f"{len(plan_contract.core_mechanics)} mechanics / {len(plan_contract.progression_plan)} progression beats",
        "contribution_score": 4.3,
        "shared_generation_contract_hash": shared_contract_hash,
        "strict_vertex_only": strict_vertex_only,
        "gdd_source": gdd_source,
        "plan_source": plan_source,
        "gdd_usage": gdd_usage,
        "plan_usage": plan_usage,
        "usage": usage,
        "model": str(generated_contract.meta.get("model") or generated.meta.get("model") or "").strip() or None,
    }
    return append_log(
        state,
        stage=PipelineStage.PLAN,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.PLANNER,
        message="기획 계약 생성 완료: 메커닉/진행/밸런스 기준 확정.",
        metadata=meta,
    )
