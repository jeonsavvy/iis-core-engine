from app.orchestration.graph.pipeline_graph import _route_after_qa_quality
from app.schemas.pipeline import PipelineStatus


def test_route_after_qa_quality_moves_to_release_in_running_state() -> None:
    state = {
        "status": PipelineStatus.RUNNING,
        "needs_rebuild": True,
        "qa_attempt": 1,
        "max_qa_loops": 3,
    }
    assert _route_after_qa_quality(state) == "Release"


def test_route_after_qa_quality_stops_on_error() -> None:
    state = {
        "status": PipelineStatus.ERROR,
        "needs_rebuild": True,
        "qa_attempt": 3,
        "max_qa_loops": 3,
    }
    assert _route_after_qa_quality(state) == "End"


def test_route_after_qa_quality_stops_on_retry() -> None:
    state = {
        "status": PipelineStatus.RETRY,
        "needs_rebuild": False,
        "qa_attempt": 1,
        "max_qa_loops": 3,
    }
    assert _route_after_qa_quality(state) == "End"
