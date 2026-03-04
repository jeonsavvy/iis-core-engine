from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate, classify_vertex_unavailable_reason
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import AnalyzeContractPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _validation_error_detail(exc: Exception) -> object:
    if isinstance(exc, ValidationError):
        return exc.errors()
    return str(exc)


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
    generation_source = str(generated.meta.get("generation_source", "stub")).strip().casefold()
    settings = _deps.vertex_service.settings
    strict_vertex_only = bool(getattr(settings, "strict_vertex_only", True))
    if strict_vertex_only and generation_source != "vertex":
        reason, retryable = classify_vertex_unavailable_reason(
            default_reason="analyze_contract_unavailable",
            generation_meta=generated.meta,
        )
        state["status"] = PipelineStatus.RETRY if retryable else PipelineStatus.ERROR
        state["reason"] = reason
        return append_log(
            state,
            stage=PipelineStage.ANALYZE,
            status=state["status"],
            agent_name=PipelineAgentName.ANALYZER,
            message="분석 지연: Vertex analyze contract를 확보하지 못했습니다."
            if retryable
            else "분석 중단: Vertex analyze contract를 확보하지 못했습니다.",
            reason=state["reason"],
            metadata={
                "generation_source": generation_source,
                "strict_vertex_only": strict_vertex_only,
                "retryable": retryable,
                "upstream_reason": str(generated.meta.get("reason", "")).strip() or None,
                "vertex_error": str(generated.meta.get("vertex_error", "")).strip() or None,
                "deliverables": ["analyze_contract_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
        )
    try:
        analyze_contract = AnalyzeContractPayload.model_validate(generated.payload)
    except Exception as exc:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = "analyze_contract_invalid"
        return append_log(
            state,
            stage=PipelineStage.ANALYZE,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.ANALYZER,
            message="분석 중단: analyze contract payload 검증에 실패했습니다.",
            reason=state["reason"],
            metadata={
                "generation_source": generation_source,
                "strict_vertex_only": strict_vertex_only,
                "validation_error": _validation_error_detail(exc),
                "deliverables": ["analyze_contract_gate"],
                "contract_status": "fail",
                **generated.meta,
            },
        )
    state["outputs"]["analyze_contract"] = analyze_contract.model_dump()
    state["outputs"]["analyze_contract_source"] = generation_source
    state["outputs"]["analyze_contract_meta"] = dict(generated.meta)
    pipeline_version = str(state["outputs"].get("pipeline_version", "forgeflow-v1"))
    usage = generated.meta.get("usage", {}) if isinstance(generated.meta.get("usage", {}), dict) else {}
    model_name = str(generated.meta.get("model", "")).strip()
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
            "strict_vertex_only": strict_vertex_only,
            "usage": usage,
            "model": model_name,
            **generated.meta,
        },
    )
