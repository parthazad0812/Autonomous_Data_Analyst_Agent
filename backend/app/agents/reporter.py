"""
Reporter Agent — LangGraph node.
Synthesizes all findings into a comprehensive Markdown report.
"""

import json
import os
import time
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AnalysisState
from app.agents.llm_client import get_creative_llm
from app.agents.utils import make_step_record, summarise_findings, extract_text_from_response
from app.agents.prompts.report_prompt import REPORT_SYSTEM, REPORT_USER_TEMPLATE


def reporter_node(state: AnalysisState) -> AnalysisState:
    """Synthesize all findings into a comprehensive Markdown report."""
    start = time.time()
    agent_name = "reporter"
    step_index = len(state.get("step_records", []))

    profile = state.get("dataset_profile", {})
    all_findings = state.get("findings", [])
    step_records = state.get("step_records", [])

    # Calculate total analysis duration
    total_duration = sum(s.get("duration_seconds", 0) for s in step_records)

    # Separate findings by type (stats findings are sent once, in their own section)
    stats_findings = [f for f in all_findings if f["agent_name"] == "statistician"]
    other_findings = [f for f in all_findings if f["agent_name"] != "statistician"]
    stats_summary = _findings_with_evidence(stats_findings, max_chars=3500)
    all_findings_text = summarise_findings(all_findings, max_chars=8000)  # fallback report text

    try:
        user_msg = REPORT_USER_TEMPLATE.format(
            dataset_filename=state.get("dataset_filename", "dataset"),
            rows=profile.get("rows", "?"),
            columns=profile.get("columns", "?"),
            generated=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            duration=f"{total_duration:.1f} seconds",
            user_query=state.get("user_query", "Comprehensive data analysis"),
            verified_stats=_verified_stats_text(profile),
            charts_text=_charts_text(all_findings),
            all_findings_text=_findings_with_evidence(other_findings, max_chars=5000)
                              or "No specific findings were generated.",
            stats_summary=stats_summary or "No statistical tests were run.",
        )

        llm = get_creative_llm()
        response = llm.invoke([
            SystemMessage(content=REPORT_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        report_md = extract_text_from_response(response.content).strip()

        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="completed",
            message=f"Report generated: {len(report_md)} characters",
            code_output=report_md[:500] + "..." if len(report_md) > 500 else report_md,
            duration_seconds=round(time.time() - start, 2),
            output_data={"report_length": len(report_md)},
        )

        return {
            **state,
            "report_markdown": report_md,
            "current_agent": "done",
            "step_records": state.get("step_records", []) + [step],
        }

    except Exception as e:
        # Fallback: write a minimal report from findings
        fallback = _generate_fallback_report(state, all_findings_text, total_duration)
        step = make_step_record(
            agent_name=agent_name,
            step_index=step_index,
            status="failed",
            message="Reporter used fallback due to LLM error",
            error_message=str(e),
            duration_seconds=round(time.time() - start, 2),
        )
        return {
            **state,
            "report_markdown": fallback,
            "current_agent": "done",
            "error_count": state.get("error_count", 0) + 1,
            "step_records": state.get("step_records", []) + [step],
        }


def _verified_stats_text(profile: dict) -> str:
    """Render the upload-time pandas profile (columns_meta) as compact text for the prompt."""
    rows = profile.get("rows", 0) or 0
    lines = []
    for c in profile.get("columns_meta", []):
        line = f"- {c.get('name')} ({c.get('col_type', c.get('dtype', '?'))}): missing {c.get('null_count', 0)}"
        if c.get("unique_count") is not None:
            line += f", unique {c['unique_count']}"
        if c.get("col_type") == "numeric":
            r = {k: round(c[k], 2) if isinstance(c.get(k), float) else c.get(k)
                 for k in ("mean", "std", "min", "p50", "max")}
            line += (f", mean {r['mean']}, std {r['std']}, min {r['min']}, "
                     f"median {r['p50']}, max {r['max']}")
        elif c.get("top_values"):
            line += f", top values {c['top_values']}"
        lines.append(line)
    missing = sum(c.get("null_count", 0) for c in profile.get("columns_meta", []))
    cells = rows * (profile.get("columns", 0) or 0)
    completeness = f"{100 * (1 - missing / cells):.1f}%" if cells else "?"
    header = f"Rows: {rows}, Columns: {profile.get('columns', '?')}, Missing cells: {missing}, Completeness: {completeness}"
    return "\n".join([header] + lines) if lines else header


def _findings_with_evidence(findings: list, max_chars: int) -> str:
    """Like summarise_findings, but keeps each finding's evidence (where the numbers live)."""
    lines = []
    for f in findings:
        evidence = json.dumps(f.get("evidence") or {}, default=str)[:300]
        lines.append(f"[{f['finding_id']}] {f['title']} ({f['confidence']} confidence): "
                     f"{f['description'][:200]} | evidence: {evidence}")
    return "\n".join(lines)[:max_chars]


def _charts_text(findings: list) -> str:
    charts = [(os.path.basename(f["visualization_path"]), f["title"]) for f in findings
              if f["finding_type"] == "visualization" and (f["visualization_path"] or "").startswith("charts/")]
    if not charts:
        return "No charts were generated. Do not embed or reference any chart."
    return "\n".join(f"- {name}: {title}" for name, title in charts)


def _generate_fallback_report(state: AnalysisState, findings_text: str, duration: float) -> str:
    """Minimal fallback report when LLM call fails."""
    profile = state.get("dataset_profile", {})
    return f"""# {state.get("dataset_filename", "Dataset")} — Analytical Report

**Generated**: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
**Dataset**: {profile.get("rows", "?")} rows × {profile.get("columns", "?")} columns
**Analysis Duration**: {duration:.1f}s
**User Query**: {state.get("user_query", "N/A")}

## Key Findings

{findings_text or "No findings were collected during this analysis."}

## Charts

{len(state.get("chart_paths", []))} visualizations were generated and stored.

---
*Report generated by the Autonomous Data Analyst Agent.*
"""
