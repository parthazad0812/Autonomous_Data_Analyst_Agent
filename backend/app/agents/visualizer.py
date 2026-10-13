"""
Visualizer Agent — LangGraph node.
Generates charts for key findings, uploads PNGs to MinIO.
"""

import os
import time
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AnalysisState, FindingRecord
from app.agents.llm_client import get_llm
from app.agents.utils import make_step_record, parse_findings_from_output, normalise_finding, extract_code_block, summarise_findings, extract_text_from_response
from app.agents.prompts.viz_prompt import VIZ_SYSTEM, VIZ_USER_TEMPLATE
from app.agents.tools.code_executor import execute_python
from app.agents.tools.data_tools import upload_chart_to_minio


def _link_charts_to_findings(findings: list[FindingRecord], uploaded_paths: list[str]) -> list[FindingRecord]:
    """
    The LLM labels charts by id ("V001"), but the API, UI and PDF need the MinIO path
    ("charts/<session>/V001.png"). Match by file stem, then assign leftovers in order;
    any uploaded chart without a finding gets a minimal visualization finding.
    """
    by_stem = {os.path.splitext(os.path.basename(p))[0]: p for p in uploaded_paths}
    unused = list(uploaded_paths)
    viz = [f for f in findings if f["finding_type"] == "visualization"]

    for f in viz:
        key = os.path.splitext(os.path.basename(f["visualization_path"] or ""))[0]
        path = by_stem.get(key) or by_stem.get(f["finding_id"])
        if path and path in unused:
            f["visualization_path"] = path
            unused.remove(path)

    for f in viz:
        if not (f["visualization_path"] or "").startswith("charts/") and unused:
            f["visualization_path"] = unused.pop(0)

    for path in unused:
        stem = os.path.splitext(os.path.basename(path))[0]
        findings.append(FindingRecord(
            finding_id=stem, agent_name="visualizer", finding_type="visualization",
            title=f"Chart {stem}", description="", evidence={"chart_id": stem},
            confidence="medium", hypothesis="", visualization_path=path,
        ))
    return findings


def visualizer_node(state: AnalysisState) -> AnalysisState:
    """Generate visualizations for key findings and store them in MinIO."""
    start = time.time()
    agent_name = "visualizer"
    step_index = len(state.get("step_records", []))

    profile = state.get("dataset_profile", {})
    dataset_path = state.get("_local_dataset_path", "")
    charts_dir = state.get("_charts_dir", "")
    session_id = state["session_id"]

    # Build a clear findings summary for the LLM
    all_findings = state.get("findings", [])
    findings_summary = summarise_findings(all_findings, max_chars=3000)

    try:
        user_msg = VIZ_USER_TEMPLATE.format(
            dataset_filename=state.get("dataset_filename", "dataset"),
            rows=profile.get("rows", "?"),
            columns=profile.get("columns", "?"),
            numeric_cols=profile.get("numeric_cols", []),
            text_cols=profile.get("text_cols", []),
            findings_summary=findings_summary or "No prior findings; create exploratory charts.",
            user_query=state.get("user_query", ""),
        )

        llm = get_llm()
        messages = [
            SystemMessage(content=VIZ_SYSTEM),
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
            
            # If code execution failed (e.g. SyntaxError, KeyError), append assistant response & error message to retry
            if attempt < max_attempts - 1:
                # keep only the latest failed attempt: bounded prompt size, fewer tokens per retry
                messages = messages[:2] + [response]
                fix_prompt = (
                    f"The code execution failed with the following error:\n\n{exec_result['stderr']}\n\n"
                    "Please fix the code. Keep it concise, focused, and under 150 lines (long code gets truncated). "
                    "Ensure all parentheses, brackets, quotes are closed, column names match the dataset, and syntax is valid, and return ONLY the complete corrected Python code."
                )
                messages.append(HumanMessage(content=fix_prompt))

        # Upload any chart files to MinIO
        uploaded_paths: list[str] = []
        for chart_file in exec_result.get("chart_files", []):
            if os.path.isfile(chart_file):
                try:
                    minio_path = upload_chart_to_minio(chart_file, session_id)
                    uploaded_paths.append(minio_path)
                except Exception:
                    pass  # Don't fail the whole agent for a bad chart

        # Parse visualization findings
        raw_findings = parse_findings_from_output(exec_result["stdout"])
        new_findings = [normalise_finding(f, agent_name, i + 1) for i, f in enumerate(raw_findings)]
        new_findings = _link_charts_to_findings(new_findings, uploaded_paths)

        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="completed" if exec_result["success"] else "failed",
            message=f"Visualizations created: {len(uploaded_paths)} charts uploaded to MinIO",
            code_executed=code,
            code_output=exec_result["stdout"],
            error_message=exec_result["stderr"],
            duration_seconds=round(time.time() - start, 2),
            output_data={"chart_paths": uploaded_paths, "findings_count": len(new_findings)},
        )

        return {
            **state,
            "findings": state.get("findings", []) + new_findings,
            "chart_paths": state.get("chart_paths", []) + uploaded_paths,
            "current_agent": "reporter",
            "step_records": state.get("step_records", []) + [step],
            "error_count": state.get("error_count", 0) + (0 if exec_result["success"] else 1),
        }

    except Exception as e:
        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="failed",
            message="Visualizer agent failed",
            error_message=str(e),
            duration_seconds=round(time.time() - start, 2),
        )
        return {
            **state,
            "current_agent": "reporter",
            "error_count": state.get("error_count", 0) + 1,
            "step_records": state.get("step_records", []) + [step],
        }
