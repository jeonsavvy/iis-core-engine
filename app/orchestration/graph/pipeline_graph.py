from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes import architect, builder, echo, publisher, qa_failed, sentinel, stylist, trigger
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineStatus


def _route_after_trigger(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Architect"


def _route_after_plan(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Stylist"


def _route_after_style(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Builder"


def _route_after_build(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Sentinel"


def _route_after_qa(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    if state["needs_rebuild"]:
        if state["qa_attempt"] >= state["max_qa_loops"]:
            return "QaFailed"
        return "Builder"
    return "Publisher"


def _route_after_publish(state: PipelineState) -> str:
    if state["status"] in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
        return "End"
    return "Echo"


def build_pipeline_graph(deps: NodeDependencies):
    graph = StateGraph(PipelineState)

    graph.add_node("Trigger", lambda state: trigger.run(state, deps))
    graph.add_node("Architect", lambda state: architect.run(state, deps))
    graph.add_node("Stylist", lambda state: stylist.run(state, deps))
    graph.add_node("Builder", lambda state: builder.run(state, deps))
    graph.add_node("Sentinel", lambda state: sentinel.run(state, deps))
    graph.add_node("QaFailed", lambda state: qa_failed.run(state, deps))
    graph.add_node("Publisher", lambda state: publisher.run(state, deps))
    graph.add_node("Echo", lambda state: echo.run(state, deps))

    graph.set_entry_point("Trigger")
    graph.add_conditional_edges(
        "Trigger",
        _route_after_trigger,
        {
            "Architect": "Architect",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Architect",
        _route_after_plan,
        {
            "Stylist": "Stylist",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Stylist",
        _route_after_style,
        {
            "Builder": "Builder",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Builder",
        _route_after_build,
        {
            "Sentinel": "Sentinel",
            "End": END,
        },
    )
    graph.add_conditional_edges(
        "Sentinel",
        _route_after_qa,
        {
            "Builder": "Builder",
            "QaFailed": "QaFailed",
            "Publisher": "Publisher",
            "End": END,
        },
    )
    graph.add_edge("QaFailed", END)
    graph.add_conditional_edges(
        "Publisher",
        _route_after_publish,
        {
            "Echo": "Echo",
            "End": END,
        },
    )
    graph.add_edge("Echo", END)

    return graph.compile()
