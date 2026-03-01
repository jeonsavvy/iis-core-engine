from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes import architect, builder, echo, publisher, qa_failed, qa_quality, sentinel, stylist, trigger
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineStatus


def _route_after_analyze(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Planner"


def _route_after_plan(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Designer"


def _route_after_design(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Developer"


def _route_after_build(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "QaRuntime"


def _route_after_qa_runtime(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    if state["needs_rebuild"]:
        if state["qa_attempt"] >= state["max_qa_loops"]:
            return "QaFailed"
        return "Developer"
    return "QaQuality"


def _route_after_qa_quality(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    if state["needs_rebuild"]:
        if state["qa_attempt"] >= state["max_qa_loops"]:
            return "QaFailed"
        return "Developer"
    return "Release"


def _route_after_release(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Report"


def build_pipeline_graph(deps: NodeDependencies):
    graph = StateGraph(PipelineState)

    graph.add_node("Analyze", lambda state: trigger.run(state, deps))
    graph.add_node("Planner", lambda state: architect.run(state, deps))
    graph.add_node("Designer", lambda state: stylist.run(state, deps))
    graph.add_node("Developer", lambda state: builder.run(state, deps))
    graph.add_node("QaRuntime", lambda state: sentinel.run(state, deps))
    graph.add_node("QaQuality", lambda state: qa_quality.run(state, deps))
    graph.add_node("QaFailed", lambda state: qa_failed.run(state, deps))
    graph.add_node("Release", lambda state: publisher.run(state, deps))
    graph.add_node("Report", lambda state: echo.run(state, deps))

    graph.set_entry_point("Analyze")
    graph.add_conditional_edges(
        "Analyze",
        _route_after_analyze,
        {
            "Planner": "Planner",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Planner",
        _route_after_plan,
        {
            "Designer": "Designer",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Designer",
        _route_after_design,
        {
            "Developer": "Developer",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Developer",
        _route_after_build,
        {
            "QaRuntime": "QaRuntime",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "QaRuntime",
        _route_after_qa_runtime,
        {
            "Developer": "Developer",
            "QaFailed": "QaFailed",
            "QaQuality": "QaQuality",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "QaQuality",
        _route_after_qa_quality,
        {
            "Developer": "Developer",
            "QaFailed": "QaFailed",
            "Release": "Release",
            "End": END,
        },
    )
    graph.add_edge("QaFailed", END)
    graph.add_conditional_edges(
        "Release",
        _route_after_release,
        {
            "Report": "Report",
            "End": END,
        },
    )
    graph.add_edge("Report", END)

    return graph.compile()
