"""
Unit tests for the Statistician Agent node.
"""

from unittest.mock import patch, MagicMock
from app.agents.statistician import statistician_node
from app.agents.state import AnalysisState


def test_statistician_node_skips_when_no_numeric_cols():
    """Test statistician agent skips gracefully when dataset has no numeric columns."""
    initial_state: AnalysisState = {
        "session_id": "test_s3",
        "dataset_filename": "text_only.csv",
        "dataset_profile": {"rows": 5, "columns": 2, "numeric_cols": []},
        "user_query": "Analyze dataset",
        "analysis_plan": {},
        "current_agent": "statistician",
        "findings": [],
        "chart_paths": [],
        "report_markdown": "",
        "error_count": 0,
        "step_records": [],
    }

    next_state = statistician_node(initial_state)

    assert next_state["current_agent"] == "visualizer"
    assert len(next_state["step_records"]) == 1
    assert next_state["step_records"][0]["status"] == "skipped"


@patch("app.agents.statistician.execute_python")
@patch("app.agents.statistician.get_llm")
def test_statistician_node_executes_tests(mock_get_llm, mock_execute):
    """Test statistician agent node runs ANOVA / t-test code and parses findings."""
    mock_response = MagicMock()
    mock_response.content = "```python\nprint('[FINDING] Type: hypothesis_test | Title: ANOVA F=12.4 p=0.001 | Evidence: {\"p_value\": 0.001}')\n```"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    findings_json = '[{"type": "hypothesis_test", "title": "ANOVA F=12.4 p=0.001", "description": "Significant difference", "confidence": "high"}]'
    mock_execute.return_value = {
        "success": True,
        "stdout": f"FINDINGS_JSON:{findings_json}",
        "stderr": "",
        "chart_files": [],
    }

    initial_state: AnalysisState = {
        "session_id": "test_s4",
        "dataset_filename": "data.csv",
        "dataset_profile": {"rows": 20, "columns": 3, "numeric_cols": ["sales"]},
        "user_query": "Test region differences",
        "analysis_plan": {},
        "current_agent": "statistician",
        "findings": [{
            "finding_id": "E001",
            "agent_name": "eda",
            "title": "Region diff",
            "description": "Sales differ across regions",
            "confidence": "high",
            "hypothesis": "Sales differ by region"
        }],
        "chart_paths": [],
        "report_markdown": "",
        "error_count": 0,
        "step_records": [],
        "_local_dataset_path": "/tmp/data.csv",
        "_charts_dir": "/tmp/charts",
    }

    next_state = statistician_node(initial_state)

    assert next_state["current_agent"] == "visualizer"
    assert len(next_state["findings"]) == 2
    assert next_state["findings"][1]["agent_name"] == "statistician"
    assert "ANOVA" in next_state["findings"][1]["title"]
