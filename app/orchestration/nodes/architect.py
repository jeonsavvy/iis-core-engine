from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate, classify_vertex_unavailable_reason
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import GDDPayload, PlanContractPayload
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
    meta = {
        "reference_count": len(research_summary["references"]),
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
