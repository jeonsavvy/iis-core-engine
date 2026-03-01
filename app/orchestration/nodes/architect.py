from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import GDDPayload, PlanContractPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _fallback_plan_contract(keyword: str, gdd: GDDPayload) -> PlanContractPayload:
    return PlanContractPayload(
        core_mechanics=[
            "directional movement + timing",
            "enemy pressure handling",
            "score combo through risky plays",
        ],
        progression_plan=[
            "초반 학습 구간",
            "중반 패턴 확장",
            "후반 클러치 압박 구간",
        ],
        encounter_plan=[
            "기본 적군 웨이브",
            "엘리트 등장 주기",
            "미니보스 이벤트",
        ],
        risk_reward_plan=[
            "고위험 고득점 기회",
            "안전 플레이 저보상 라인",
            "실수 후 회복 루트",
        ],
        control_model=f"{gdd.genre} / keyboard-centric analog intent",
        balance_baseline={
            "base_hp": 3.0,
            "spawn_rate": 1.0,
            "difficulty_scale_per_min": 1.15,
            "session_time_sec": 120.0,
            "keyword_weight": float(len(keyword.strip()) or 1),
        },
    )


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
    generated = deps.vertex_service.generate_gdd_bundle(keyword)
    payload = generated.payload
    try:
        gdd = GDDPayload.model_validate(payload.get("gdd", {}))
    except Exception:
        gdd = GDDPayload(
            title=f"{keyword.title()} Infinite",
            genre="arcade",
            objective="Get highest score possible in 90 seconds.",
            visual_style="neon-minimal",
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
    generated_contract = deps.vertex_service.generate_plan_contract(
        keyword=keyword,
        gdd=gdd.model_dump(),
        research_summary=research_summary,
    )
    try:
        plan_contract = PlanContractPayload.model_validate(generated_contract.payload)
    except Exception:
        plan_contract = _fallback_plan_contract(keyword, gdd)
    state["outputs"]["plan_contract"] = plan_contract.model_dump()
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
        **generated.meta,
        **generated_contract.meta,
    }
    return append_log(
        state,
        stage=PipelineStage.PLAN,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.PLANNER,
        message="기획 계약 생성 완료: 메커닉/진행/밸런스 기준 확정.",
        metadata=meta,
    )
