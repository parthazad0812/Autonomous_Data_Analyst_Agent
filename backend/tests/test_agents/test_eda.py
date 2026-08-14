"""
Unit tests for the EDA Agent node.
"""

from unittest.mock import patch, MagicMock
from app.agents.eda import eda_node
from app.agents.state import AnalysisState


@patch("app.agents.eda.execute_python")
@patch("app.agents.eda.get_llm")
def test_eda_node_success(mock_get_llm, mock_execute):
    """Test EDA agent node executes analysis and appends EDA findings."""
    mock_response = MagicMock()
    mock_response.content = "```python\nprint('[FINDING] Type: correlation | Title: High correlation between sales and units')\n```"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    findings_json = '[{"type": "correlation", "title": "High correlation between sales and units", "description": "Correlation is 0.95", "confidence": "high"}]'
    mock_execute.return_value = {
        "success": True,
        "stdout": f"FINDINGS_JSON:{findings_json}",
        "stderr": "",
        "chart_files": [],
    }

    initial_state: AnalysisState = {
        "session_id": "test_s2",
        "dataset_filename": "sales.csv",
        "dataset_profile": {"rows": 10, "columns": 3, "numeric_cols": ["sales", "units"]},
        "user_query": "Explore correlations",
        "analysis_plan": {},
        "current_agent": "eda",
        "findings": [],
        "chart_paths": [],
        "report_markdown": "",
        "error_count": 0,
        "step_records": [],
        "_local_dataset_path": "/tmp/sales.csv",
        "_charts_dir": "/tmp/charts",
    }

    next_state = eda_node(initial_state)

    assert next_state["current_agent"] == "statistician"
    assert len(next_state["findings"]) == 1
    assert next_state["findings"][0]["agent_name"] == "eda"
    assert "High correlation" in next_state["findings"][0]["title"]
