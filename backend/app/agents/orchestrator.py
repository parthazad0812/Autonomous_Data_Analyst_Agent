"""
Orchestrator Agent — LangGraph node.
Creates the analysis plan, updates session in DB, broadcasts the plan.
"""

import json
import time
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AnalysisState
from app.agents.llm_client import get_llm
from app.agents.utils import make_step_record, extract_text_from_response
from app.agents.prompts.orchestrator_prompt import ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER_TEMPLATE


def orchestrator_node(state: AnalysisState) -> AnalysisState:
    """Plan the analysis strategy for this dataset."""
    start = time.time()
    agent_name = "orchestrator"
    step_index = len(state.get("step_records", []))

    try:
        profile = state.get("dataset_profile", {})
        profile_summary = (
            f"Rows: {profile.get('rows', '?')}, "
            f"Columns: {profile.get('columns', '?')}, "
            f"Column names: {profile.get('column_names', [])}, "
            f"Numeric cols: {profile.get('numeric_cols', [])}, "
            f"Text cols: {profile.get('text_cols', [])}, "
            f"Datetime cols: {profile.get('datetime_cols', [])}, "
            f"Has nulls: {profile.get('has_nulls', False)}"
        )

        user_msg = ORCHESTRATOR_USER_TEMPLATE.format(
            profile_summary=profile_summary,
            user_query=state.get("user_query", "Perform a comprehensive analysis"),
            dataset_filename=state.get("dataset_filename", "dataset"),
        )

        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=ORCHESTRATOR_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        raw = extract_text_from_response(response.content).strip()

        # Strip markdown fences if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        analysis_plan = json.loads(raw)

        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="completed",
            message=f"Analysis plan created: {analysis_plan.get('analysis_plan', {}).get('summary', '')}",
            code_output=json.dumps(analysis_plan, indent=2),
            duration_seconds=round(time.time() - start, 2),
            output_data=analysis_plan,
        )

        return {
            **state,
            "analysis_plan": analysis_plan,
            "current_agent": "profiler",
            "step_records": state.get("step_records", []) + [step],
        }

    except Exception as e:
        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="failed",
            message="Orchestrator failed to create plan",
            error_message=str(e),
            duration_seconds=round(time.time() - start, 2),
        )
        # Use a fallback plan so the pipeline continues
        fallback_plan = {
            "analysis_plan": {
                "summary": "Comprehensive statistical analysis",
                "estimated_steps": 5,
                "key_questions": [state.get("user_query", "")],
                "phases": [],
            }
        }
        return {
            **state,
            "analysis_plan": fallback_plan,
            "current_agent": "profiler",
            "error_count": state.get("error_count", 0) + 1,
            "step_records": state.get("step_records", []) + [step],
        }
