"""
Unit tests for the LangGraph Analysis Graph compilation and pipeline topology.
"""

from app.agents.graph import build_analysis_graph, analysis_graph


def test_build_analysis_graph_nodes():
    """Test that build_analysis_graph contains all 6 agent nodes."""
    graph = build_analysis_graph()
    assert graph is not None
    
    # Verify graph node keys
    nodes = list(graph.nodes.keys())
    assert "orchestrator" in nodes
    assert "profiler" in nodes
    assert "eda" in nodes
    assert "statistician" in nodes
    assert "visualizer" in nodes
    assert "reporter" in nodes


def test_analysis_graph_instance_exists():
    """Test pre-compiled graph instance is compiled and ready for invocation."""
    assert analysis_graph is not None
