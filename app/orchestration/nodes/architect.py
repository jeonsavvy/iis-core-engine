from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import GDDPayload, PlanContractPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


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

    keyword = state["keyword"]
    settings = deps.vertex_service.settings
    strict_vertex_only = bool(getattr(settings, "strict_vertex_only", True))
    generated = deps.vertex_service.generate_gdd_bundle(keyword)
    gdd_source = str(generated.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and gdd_source != "vertex":
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "gdd_unavailable"
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PLANNER,
            message="기획 중단: Vertex GDD를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "generation_source": gdd_source,
                "strict_vertex_only": strict_vertex_only,
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
    generated_contract = deps.vertex_service.generate_plan_contract(
        keyword=keyword,
        gdd=gdd.model_dump(),
        research_summary=research_summary,
    )
    plan_source = str(generated_contract.meta.get("generation_source", "stub")).strip().casefold()
    if strict_vertex_only and plan_source != "vertex":
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "plan_contract_unavailable"
        return append_log(
            state,
            stage=PipelineStage.PLAN,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.PLANNER,
            message="기획 중단: Vertex plan contract를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "gdd_source": gdd_source,
                "plan_source": plan_source,
                "strict_vertex_only": strict_vertex_only,
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
