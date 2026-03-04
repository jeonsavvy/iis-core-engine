from uuid import uuid4

from app.orchestration.nodes.common import append_log
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _state():
    return {
        "pipeline_id": uuid4(),
        "keyword": "test",
        "qa_attempt": 0,
        "max_qa_loops": 3,
        "fail_qa_until": 0,
        "build_iteration": 0,
        "needs_rebuild": False,
        "status": PipelineStatus.RUNNING,
        "reason": None,
        "logs": [],
        "flushed_log_count": 0,
        "log_sink": None,
        "outputs": {},
    }


def test_append_log_injects_lane_and_handoff_for_success_stage():
    state = _state()
    append_log(
        state,
        stage=PipelineStage.ANALYZE,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.ANALYZER,
        message="분석 계약 생성 완료",
    )
    record = state["logs"][-1]
    assert record.metadata["agent_lane"] == "A"
    assert record.metadata["handoff_to_stage"] == PipelineStage.PLAN.value
    assert record.metadata["handoff_summary"] == "분석 계약 생성 완료"


def test_append_log_does_not_override_existing_metadata():
    state = _state()
    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.ERROR,
        agent_name=PipelineAgentName.DEVELOPER,
        message="빌드 실패",
        metadata={
            "agent_lane": "B",
            "handoff_to_stage": PipelineStage.RELEASE.value,
            "handoff_summary": "custom handoff",
        },
    )
    record = state["logs"][-1]
    assert record.metadata["agent_lane"] == "B"
    assert record.metadata["handoff_to_stage"] == PipelineStage.RELEASE.value
    assert record.metadata["handoff_summary"] == "custom handoff"


def test_append_log_adds_lane_for_qa_quality():
    state = _state()
    append_log(
        state,
        stage=PipelineStage.QA_QUALITY,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.QA_QUALITY,
        message="품질 게이트 완료",
    )
    record = state["logs"][-1]
    assert record.metadata["agent_lane"] == "B"
    assert record.metadata["handoff_to_stage"] == PipelineStage.RELEASE.value
