"""
Profiler Agent — LangGraph node.
Generates and executes deep data profiling code.
"""

import time
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AnalysisState
from app.agents.llm_client import get_llm
from app.agents.utils import make_step_record, parse_findings_from_output, normalise_finding, extract_code_block, extract_text_from_response
from app.agents.prompts.profiler_prompt import PROFILER_SYSTEM, PROFILER_USER_TEMPLATE
from app.agents.tools.code_executor import execute_python


def profiler_node(state: AnalysisState) -> AnalysisState:
    """Generate and run deep data profiling code."""
    start = time.time()
    agent_name = "profiler"
    step_index = len(state.get("step_records", []))

    profile = state.get("dataset_profile", {})
    dataset_path = state.get("_local_dataset_path", "")
    charts_dir = state.get("_charts_dir", "")
    session_id = state["session_id"]

    try:
        user_msg = PROFILER_USER_TEMPLATE.format(
            dataset_filename=state.get("dataset_filename", "dataset"),
            rows=profile.get("rows", "?"),
            columns=profile.get("columns", "?"),
            column_names=profile.get("column_names", []),
            dtypes=[c.get("dtype", "") for c in profile.get("columns_meta", [])],
            null_counts={c.get("name"): c.get("null_count", 0) for c in profile.get("columns_meta", [])},
            sample=str(profile.get("sample_rows", [])[:3]),
            user_query=state.get("user_query", ""),
        )

        llm = get_llm()
        messages = [
            SystemMessage(content=PROFILER_SYSTEM),
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
                timeout=120,
            )

            if exec_result["success"]:
                break

            if attempt < max_attempts - 1:
                messages.append(response)
                fix_prompt = (
                    f"The code execution failed with the following error:\n\n{exec_result['stderr']}\n\n"
                    "Please fix the code. Keep it concise, focused, and under 150 lines. "
                    "Ensure all syntax is valid, all brackets/parentheses/quotes are properly closed, and return ONLY the complete corrected Python code."
                )
                messages.append(HumanMessage(content=fix_prompt))

        raw_findings = parse_findings_from_output(exec_result["stdout"])
        new_findings = [normalise_finding(f, agent_name, i + 1) for i, f in enumerate(raw_findings)]

        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="completed" if exec_result["success"] else "failed",
            message=f"Profiling complete: {len(new_findings)} findings",
            code_executed=code,
            code_output=exec_result["stdout"],
            error_message=exec_result["stderr"],
            duration_seconds=round(time.time() - start, 2),
            output_data={"findings_count": len(new_findings)},
        )

        return {
            **state,
            "findings": state.get("findings", []) + new_findings,
            "current_agent": "eda",
            "step_records": state.get("step_records", []) + [step],
            "error_count": state.get("error_count", 0) + (0 if exec_result["success"] else 1),
        }

    except Exception as e:
        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="failed",
            message="Profiler agent failed",
            error_message=str(e),
            duration_seconds=round(time.time() - start, 2),
        )
        return {
            **state,
            "current_agent": "eda",
            "error_count": state.get("error_count", 0) + 1,
            "step_records": state.get("step_records", []) + [step],
        }
