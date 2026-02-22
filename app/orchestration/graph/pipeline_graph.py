from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes import architect, builder, echo, publisher, qa_failed, sentinel, stylist, trigger
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineStatus


def _route_after_qa(state: PipelineState) -> str:
    if state["needs_rebuild"]:
        if state["qa_attempt"] >= state["max_qa_loops"]:
            return "QaFailed"
        return "Builder"
    return "Publisher"


def _route_after_publish(state: PipelineState) -> str:
    if state["status"] == PipelineStatus.ERROR:
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
    graph.add_edge("Trigger", "Architect")
    graph.add_edge("Architect", "Stylist")
    graph.add_edge("Stylist", "Builder")
    graph.add_edge("Builder", "Sentinel")
    graph.add_conditional_edges(
        "Sentinel",
        _route_after_qa,
        {
            "Builder": "Builder",
            "QaFailed": "QaFailed",
            "Publisher": "Publisher",
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
