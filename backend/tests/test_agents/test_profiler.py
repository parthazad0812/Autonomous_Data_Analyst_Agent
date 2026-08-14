"""
Unit tests for the Profiler Agent node.
"""

from unittest.mock import patch, MagicMock
from app.agents.profiler import profiler_node
from app.agents.state import AnalysisState


@patch("app.agents.profiler.execute_python")
@patch("app.agents.profiler.get_llm")
def test_profiler_node_success(mock_get_llm, mock_execute):
    """Test profiler_node generates code, executes it, and extracts findings."""
    # Mock LLM response
    mock_response = MagicMock()
    mock_response.content = "```python\nprint('[FINDING] Type: summary | Title: Data Profile | Desc: 4 rows 2 columns')\n```"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    # Mock code execution result
    findings_json = '[{"type": "summary", "title": "Data Profile", "description": "4 rows 2 columns", "confidence": "high"}]'
    mock_execute.return_value = {
        "success": True,
        "stdout": f"FINDINGS_JSON:{findings_json}",
        "stderr": "",
        "chart_files": [],
    }

    initial_state: AnalysisState = {
        "session_id": "test_s1",
        "dataset_filename": "data.csv",
        "dataset_profile": {"rows": 4, "columns": 2, "column_names": ["a", "b"]},
        "user_query": "Profile dataset",
        "analysis_plan": {},
        "current_agent": "profiler",
        "findings": [],
        "chart_paths": [],
        "report_markdown": "",
        "error_count": 0,
        "step_records": [],
        "_local_dataset_path": "/tmp/data.csv",
        "_charts_dir": "/tmp/charts",
    }

    next_state = profiler_node(initial_state)

    assert next_state["current_agent"] == "eda"
    assert len(next_state["findings"]) == 1
    assert next_state["findings"][0]["agent_name"] == "profiler"
    assert next_state["findings"][0]["title"] == "Data Profile"
    assert len(next_state["step_records"]) == 1
    assert next_state["step_records"][0]["status"] == "completed"
