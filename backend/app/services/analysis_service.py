"""
Analysis Service — orchestrates the full agent pipeline run.

Called from the FastAPI background task. Manages:
- DB session lifecycle (status updates, step/finding persistence)
- Download dataset from MinIO to temp file
- Build initial LangGraph state
- Run the agent graph
- Persist results back to DB
- Publish WebSocket events at each key moment
"""

import os
import json
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session as DBSession

from app.db.database import SessionLocal
from app.models.session import AnalysisSession
from app.models.step import AgentStep
from app.models.finding import Finding
from app.models.report import Report
from app.agents.graph import analysis_graph
from app.agents.state import AnalysisState
from app.agents.tools.data_tools import (
    download_dataset_to_temp,
    make_charts_temp_dir,
    cleanup_temp_files,
)
from app.api.websocket import publish_event_sync


def _publish(session_id: str, agent: str, status: str, message: str, data: dict = None):
    """Publish a structured WebSocket event."""
    publish_event_sync(session_id, {
        "type": "agent_update",
        "agent": agent,
        "status": status,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat(),
    })


def _update_session_status(db: DBSession, session_id: str, status: str):
    db.query(AnalysisSession).filter(AnalysisSession.id == session_id).update(
        {"status": status}
    )
    db.commit()


def _persist_step(db: DBSession, session_id: str, step: dict, order: int):
    """Save an AgentStepRecord to the DB."""
    output_data = step.get("output_data", {}) or {}
    # Store message in output_data since model doesn't have a message field
    output_data["message"] = step.get("message", "")
    db_step = AgentStep(
        session_id=session_id,
        agent_name=step.get("agent_name", "unknown"),
        step_index=order,
        status=step.get("status", "completed"),
        code_executed=step.get("code_executed", "") or None,
        code_output=step.get("code_output", "") or None,
        error_message=step.get("error_message", "") or None,
        duration_seconds=step.get("duration_seconds", 0.0),
        output_data=output_data,
    )
    db.add(db_step)
    db.commit()
    return db_step


def _persist_finding(db: DBSession, session_id: str, finding: dict):
    """Save a FindingRecord to the DB."""
    # Store agent_name in evidence since Finding model may not have the column yet
    evidence = finding.get("evidence", {}) or {}
    evidence["agent_name"] = finding.get("agent_name", "unknown")
    db_finding = Finding(
        session_id=session_id,
        finding_type=finding.get("finding_type", "profile"),
        title=finding.get("title", ""),
        description=finding.get("description", ""),
        evidence=evidence,
        confidence=finding.get("confidence", "medium"),
        hypothesis=finding.get("hypothesis", ""),
        visualization_path=finding.get("visualization_path", ""),
    )
    db.add(db_finding)
    db.commit()


def _persist_report(db: DBSession, session_id: str, markdown: str, chart_paths: list):
    """Save the final report to the DB."""
    db_report = Report(
        session_id=session_id,
        report_markdown=markdown,
        # chart_paths stored in audience_level field as JSON string (schema reuse)
        audience_level="balanced",
    )
    db.add(db_report)
    db.commit()


def run_analysis(session_id: str) -> None:
    """
    Main entry point — runs the full agent pipeline for a session.
    Designed to be called from a FastAPI BackgroundTask.
    """
    db = SessionLocal()
    local_dataset_path = None
    charts_dir = None

    try:
        # ── 1. Load session from DB ────────────────────────────────────────────
        session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
        if not session:
            return

        _update_session_status(db, session_id, "running")
        _publish(session_id, "orchestrator", "running", "Analysis pipeline started")

        # ── 2. Download dataset from MinIO to temp file ────────────────────────
        if not session.dataset_path:
            _publish(session_id, "orchestrator", "failed", "No dataset path found in session")
            _update_session_status(db, session_id, "failed")
            return

        local_dataset_path = download_dataset_to_temp(session.dataset_path)
        charts_dir = make_charts_temp_dir(session_id)

        # ── 3. Build the dataset profile by re-profiling the temp file ─────────
        # Re-profile the downloaded file to provide full column metadata to agents
        try:
            import pandas as pd
            ext = os.path.splitext(local_dataset_path)[1].lower()
            if ext == ".csv":
                df = pd.read_csv(local_dataset_path, low_memory=False)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(local_dataset_path, engine="openpyxl")
            elif ext == ".json":
                df = pd.read_json(local_dataset_path)
            elif ext == ".parquet":
                df = pd.read_parquet(local_dataset_path)
            else:
                df = pd.read_csv(local_dataset_path, low_memory=False)

            from app.services.upload_service import profile_dataframe
            profile = profile_dataframe(df)
            del df  # free memory
        except Exception as profile_err:
            _publish(session_id, "orchestrator", "running",
                     f"Could not re-profile dataset: {profile_err}. Using minimal metadata.")
            profile = {
                "rows": session.dataset_rows or 0,
                "columns": session.dataset_columns or 0,
                "column_names": [],
                "numeric_cols": [],
                "text_cols": [],
                "datetime_cols": [],
                "has_nulls": False,
                "memory_mb": 0.0,
                "sample_rows": [],
                "columns_meta": [],
            }

        # ── 4. Build initial LangGraph state ───────────────────────────────────
        initial_state: AnalysisState = {
            "session_id": session_id,
            "user_query": session.user_query or "Perform a comprehensive analysis of this dataset.",
            "dataset_filename": session.dataset_filename,
            "dataset_minio_path": session.dataset_path,
            "dataset_profile": profile,
            "analysis_plan": {},
            "findings": [],
            "chart_paths": [],
            "report_markdown": "",
            "step_records": [],
            "error_count": 0,
            "current_agent": "orchestrator",
            "total_llm_tokens": 0,
            "total_llm_cost": 0.0,
            # Private fields for tools (not part of TypedDict spec but stored in dict)
            "_local_dataset_path": local_dataset_path,
            "_charts_dir": charts_dir,
        }

        # ── 5. Run the graph ───────────────────────────────────────────────────
        _publish(session_id, "orchestrator", "running", "Planning analysis strategy...")

        final_state = analysis_graph.invoke(initial_state)

        # ── 6. Persist all step records ────────────────────────────────────────
        for i, step in enumerate(final_state.get("step_records", [])):
            _persist_step(db, session_id, step, i)
            _publish(
                session_id,
                step.get("agent_name", "unknown"),
                step.get("status", "completed"),
                step.get("message", ""),
                {"step_index": i, "duration": step.get("duration_seconds", 0)},
            )

        # ── 7. Persist findings ────────────────────────────────────────────────
        for finding in final_state.get("findings", []):
            _persist_finding(db, session_id, finding)

        # ── 8. Persist report ──────────────────────────────────────────────────
        report_md = final_state.get("report_markdown", "")
        if report_md:
            _persist_report(db, session_id, report_md, final_state.get("chart_paths", []))

        # ── 9. Update session with totals ──────────────────────────────────────
        db.query(AnalysisSession).filter(AnalysisSession.id == session_id).update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc),
            "analysis_plan": final_state.get("analysis_plan", {}),
        })
        db.commit()

        _publish(session_id, "reporter", "completed",
                 f"Analysis complete! {len(final_state.get('findings', []))} findings, "
                 f"{len(final_state.get('chart_paths', []))} charts, report ready.",
                 {"findings_count": len(final_state.get("findings", [])),
                  "chart_count": len(final_state.get("chart_paths", []))})

    except Exception as e:
        _publish(session_id, "orchestrator", "failed", f"Analysis pipeline failed: {str(e)}")
        try:
            _update_session_status(db, session_id, "failed")
        except Exception:
            pass

    finally:
        db.close()
        cleanup_temp_files(local_dataset_path or "", charts_dir or "")
