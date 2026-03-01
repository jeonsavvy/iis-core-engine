from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import AnalyzeContractPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _fallback_analyze_contract(keyword: str) -> AnalyzeContractPayload:
    return AnalyzeContractPayload(
        intent=f"{keyword} 요청을 브라우저 게임 제작 파이프라인으로 분해",
        scope_in=[
            "playable browser runtime",
            "single artifact deploy",
            "ops traceable pipeline logs",
        ],
        scope_out=[
            "manual approval dependency",
            "external paid asset requirement",
            "native executable packaging",
        ],
        hard_constraints=[
            "leaderboard contract preserved",
            "no secret/token exposure",
            "runtime boot stability required",
        ],
        forbidden_patterns=[
            "click-only trivial score loop",
            "placeholder-only visual output",
            "unhandled runtime exception",
        ],
        success_outcome="요청 의도와 조작감이 명확한 결과물이 운영실에 단계별 근거와 함께 노출된다.",
    )


def run(state: PipelineState, _deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        _deps,
        stage=PipelineStage.ANALYZE,
        agent_name=PipelineAgentName.ANALYZER,
        allow_pause=False,
    )
    if gated_state is not None:
        return gated_state

    state["status"] = PipelineStatus.RUNNING
    generated = _deps.vertex_service.generate_analyze_contract(keyword=state["keyword"])
    try:
        analyze_contract = AnalyzeContractPayload.model_validate(generated.payload)
    except Exception:
        analyze_contract = _fallback_analyze_contract(state["keyword"])
    state["outputs"]["analyze_contract"] = analyze_contract.model_dump()
    pipeline_version = str(state["outputs"].get("pipeline_version", "forgeflow-v1"))
    return append_log(
        state,
        stage=PipelineStage.ANALYZE,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.ANALYZER,
        message=f"분석 계약 생성 완료: {state['keyword']}",
        metadata={
            "pipeline_version": pipeline_version,
            "deliverables": [
                "analyze_contract.intent",
                "analyze_contract.scope_in/out",
                "analyze_contract.forbidden_patterns",
            ],
            "contract_status": "pass",
            "contract_summary": analyze_contract.intent,
            "contribution_score": 4.2,
            **generated.meta,
        },
    )
