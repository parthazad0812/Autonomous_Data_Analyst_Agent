"""
EDA Agent — LangGraph node.
Generates and executes exploratory data analysis code.
"""

import time
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AnalysisState
from app.agents.llm_client import get_llm
from app.agents.utils import make_step_record, parse_findings_from_output, normalise_finding, extract_code_block, summarise_findings, extract_text_from_response
from app.agents.prompts.eda_prompt import EDA_SYSTEM, EDA_USER_TEMPLATE
from app.agents.tools.code_executor import execute_python


def eda_node(state: AnalysisState) -> AnalysisState:
    """Run deep exploratory data analysis."""
    start = time.time()
    agent_name = "eda"
    step_index = len(state.get("step_records", []))

    profile = state.get("dataset_profile", {})
    dataset_path = state.get("_local_dataset_path", "")
    charts_dir = state.get("_charts_dir", "")
    session_id = state["session_id"]

    try:
        profile_findings = [f for f in state.get("findings", []) if f["agent_name"] == "profiler"]
        profile_summary = summarise_findings(profile_findings, max_chars=2000)

        user_msg = EDA_USER_TEMPLATE.format(
            dataset_filename=state.get("dataset_filename", "dataset"),
            rows=profile.get("rows", "?"),
            columns=profile.get("columns", "?"),
            numeric_cols=profile.get("numeric_cols", []),
            text_cols=profile.get("text_cols", []),
            datetime_cols=profile.get("datetime_cols", []),
            has_nulls=profile.get("has_nulls", False),
            profile_summary=profile_summary or "No profiling findings yet.",
            user_query=state.get("user_query", "Perform comprehensive EDA"),
        )

        llm = get_llm()
        messages = [
            SystemMessage(content=EDA_SYSTEM),
            HumanMessage(content=user_msg),
        ]
        
        code = ""
        exec_result = {"success": False, "stdout": "", "stderr": "", "chart_files": []}
        max_attempts = 3

        for attempt in range(max_attempts):
            response = llm.invoke(messages)
            raw_content = extract_text_from_response(response.content).strip()
            code = extract_code_block(raw_content)

            exec_result = execute_python(
                code=code,
                dataset_local_path=dataset_path,
                session_id=session_id,
                charts_dir=charts_dir,
                timeout=150,
            )

            if exec_result["success"]:
                break

            if attempt < max_attempts - 1:
                messages.append(response)
                fix_prompt = (
                    f"The code execution failed with the following error:\n\n{exec_result['stderr']}\n\n"
                    "Please fix the code (ensure all syntax is valid, column names match, and all brackets/quotes are closed) and return ONLY the complete corrected Python code."
                )
                messages.append(HumanMessage(content=fix_prompt))

        raw_findings = parse_findings_from_output(exec_result["stdout"])
        new_findings = [normalise_finding(f, agent_name, i + 1) for i, f in enumerate(raw_findings)]

        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="completed" if exec_result["success"] else "failed",
            message=f"EDA complete: {len(new_findings)} findings, "
                    f"{len(exec_result.get('chart_files', []))} charts",
            code_executed=code,
            code_output=exec_result["stdout"],
            error_message=exec_result["stderr"],
            duration_seconds=round(time.time() - start, 2),
            output_data={"findings_count": len(new_findings)},
        )

        return {
            **state,
            "findings": state.get("findings", []) + new_findings,
            "current_agent": "statistician",
            "step_records": state.get("step_records", []) + [step],
            "error_count": state.get("error_count", 0) + (0 if exec_result["success"] else 1),
        }

    except Exception as e:
        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="failed",
            message="EDA agent failed",
            error_message=str(e),
            duration_seconds=round(time.time() - start, 2),
        )
        return {
            **state,
            "current_agent": "statistician",
            "error_count": state.get("error_count", 0) + 1,
            "step_records": state.get("step_records", []) + [step],
        }
