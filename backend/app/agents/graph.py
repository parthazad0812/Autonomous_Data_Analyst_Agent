"""
LangGraph state machine — wires all 6 agent nodes into a sequential pipeline.

Pipeline:
  START → orchestrator → profiler → eda → statistician → visualizer → reporter → END

The state flows through each node; each agent reads from it and writes back.
"""

from langgraph.graph import StateGraph, END

from app.agents.state import AnalysisState
from app.agents.orchestrator import orchestrator_node
from app.agents.profiler import profiler_node
from app.agents.eda import eda_node
from app.agents.statistician import statistician_node
from app.agents.visualizer import visualizer_node
from app.agents.reporter import reporter_node


def build_analysis_graph() -> StateGraph:
    """
    Build and compile the LangGraph analysis pipeline.
    Returns a compiled runnable graph.
    """
    graph = StateGraph(AnalysisState)

    # Register all nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("profiler", profiler_node)
    graph.add_node("eda", eda_node)
    graph.add_node("statistician", statistician_node)
    graph.add_node("visualizer", visualizer_node)
    graph.add_node("reporter", reporter_node)

    # Linear pipeline with sequential edges
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "profiler")
    graph.add_edge("profiler", "eda")
    graph.add_edge("eda", "statistician")
    graph.add_edge("statistician", "visualizer")
    graph.add_edge("visualizer", "reporter")
    graph.add_edge("reporter", END)

    return graph.compile()


# Pre-compiled graph instance (import this in analysis_service)
analysis_graph = build_analysis_graph()
