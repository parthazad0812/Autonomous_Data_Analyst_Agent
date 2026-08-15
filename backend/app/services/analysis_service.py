"""
Analysis Service — orchestrates the full agent pipeline run.

Called from the FastAPI background task. Manages:
- DB session lifecycle (short-lived per-operation sessions to avoid SSL timeouts)
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
from sqlalchemy.exc import OperationalError
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


# ── WebSocket publish ─────────────────────────────────────────────────────────

def _publish(session_id: str, agent: str, status: str, message: str, data: dict = None):
    """Publish a structured WebSocket event."""
    publish_event_sync(session_id, {
        "type": "agent_update",
        "agent": agent,
        "status": status,
        "message": message,
        "data": data or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── DB helpers — each uses its own short-lived session ───────────────────────
# Using short-lived sessions is critical in production: the analysis pipeline
# runs for 2-5+ minutes with long LLM calls between DB writes.  Holding a
# single session open for that duration causes the SSL connection to be dropped
# by managed Postgres providers (Neon, Supabase, etc.) which aggressively
# terminate idle connections.  By opening and closing a fresh session for each
# individual write we completely avoid this problem.

def _db_retry(fn, max_retries: int = 2):
    """
    Execute a DB operation (lambda) with retry on transient connection errors.
    On failure, waits 1 second and retries with a brand-new session.
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except OperationalError as exc:
            if attempt >= max_retries - 1:
                raise
            time.sleep(1)


def _update_session_status(session_id: str, status: str):
    """Open a fresh session, update status, commit, close."""
    def _run():
        db = SessionLocal()
        try:
            db.query(AnalysisSession).filter(AnalysisSession.id == session_id).update(
                {"status": status}
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    _db_retry(_run)


def _load_session(session_id: str):
    """Load the AnalysisSession record in a fresh session and return a plain dict."""
    db = SessionLocal()
    try:
        session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
        if not session:
            return None
        # Detach: copy fields into a plain dict so we can close the session
        return {
            "id": session.id,
            "user_id": session.user_id,
            "title": session.title,
            "status": session.status,
            "dataset_filename": session.dataset_filename,
            "dataset_path": session.dataset_path,
            "dataset_size_bytes": session.dataset_size_bytes,
            "dataset_rows": session.dataset_rows,
            "dataset_columns": session.dataset_columns,
            "user_query": session.user_query,
        }
    finally:
        db.close()


def _persist_step(session_id: str, step: dict, order: int):
    """Open a fresh session, save an AgentStepRecord, commit, close."""
    def _run():
        db = SessionLocal()
        try:
            output_data = dict(step.get("output_data", {}) or {})
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
            db.refresh(db_step)
            return db_step.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return _db_retry(_run)


def _persist_finding(session_id: str, finding: dict):
    """Open a fresh session, save a FindingRecord, commit, close."""
    def _run():
        db = SessionLocal()
        try:
            evidence = dict(finding.get("evidence", {}) or {})
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
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    _db_retry(_run)


def _persist_report(session_id: str, markdown: str, chart_paths: list):
    """Open a fresh session, save the final Report, commit, close."""
    def _run():
        db = SessionLocal()
        try:
            db_report = Report(
                session_id=session_id,
                report_markdown=markdown,
                audience_level="balanced",
            )
            db.add(db_report)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    _db_retry(_run)


def _finalise_session(session_id: str, analysis_plan: dict):
    """Open a fresh session, mark session completed, commit, close."""
    def _run():
        db = SessionLocal()
        try:
            db.query(AnalysisSession).filter(AnalysisSession.id == session_id).update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "analysis_plan": analysis_plan,
            })
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    _db_retry(_run)


def _fail_session(session_id: str):
    """Best-effort: mark session as failed. Never raises."""
    try:
        _update_session_status(session_id, "failed")
    except Exception:
        pass


# ── Main pipeline entry point ─────────────────────────────────────────────────

def run_analysis(session_id: str) -> None:
    """
    Main entry point — runs the full agent pipeline for a session.
    Designed to be called from a FastAPI BackgroundTask.

    Each DB write uses its own short-lived session so that long LLM calls
    between writes cannot cause SSL connection timeouts.
    """
    local_dataset_path = None
    charts_dir = None

    try:
        # ── 1. Load session details ────────────────────────────────────────────
        session = _load_session(session_id)
        if not session:
            return

        _update_session_status(session_id, "running")
        _publish(session_id, "orchestrator", "running", "Analysis pipeline started")

        # ── 2. Download dataset from MinIO to temp file ────────────────────────
        if not session["dataset_path"]:
            _publish(session_id, "orchestrator", "failed", "No dataset path found in session")
            _fail_session(session_id)
            return

        local_dataset_path = download_dataset_to_temp(session["dataset_path"])
        charts_dir = make_charts_temp_dir(session_id)

        # ── 3. Build the dataset profile by re-profiling the temp file ─────────
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
            del df  # free memory immediately
        except Exception as profile_err:
            _publish(session_id, "orchestrator", "running",
                     f"Could not re-profile dataset: {profile_err}. Using minimal metadata.")
            profile = {
                "rows": session["dataset_rows"] or 0,
                "columns": session["dataset_columns"] or 0,
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
            "user_query": session["user_query"] or "Perform a comprehensive analysis of this dataset.",
            "dataset_filename": session["dataset_filename"],
            "dataset_minio_path": session["dataset_path"],
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
            "_local_dataset_path": local_dataset_path,
            "_charts_dir": charts_dir,
        }

        # ── 5. Run the graph ───────────────────────────────────────────────────
        _publish(session_id, "orchestrator", "running", "Planning analysis strategy...")

        final_state = analysis_graph.invoke(initial_state)

        # ── 6. Persist step records (each in its own short-lived session) ──────
        for i, step in enumerate(final_state.get("step_records", [])):
            try:
                _persist_step(session_id, step, i)
            except Exception as e:
                # Log but don't abort — step persistence failure shouldn't kill the whole run
                _publish(session_id, step.get("agent_name", "unknown"), "warning",
                         f"Could not persist step {i}: {e}")
            _publish(
                session_id,
                step.get("agent_name", "unknown"),
                step.get("status", "completed"),
                step.get("message", ""),
                {"step_index": i, "duration": step.get("duration_seconds", 0)},
            )

        # ── 7. Persist findings (each in its own short-lived session) ──────────
        for finding in final_state.get("findings", []):
            try:
                _persist_finding(session_id, finding)
            except Exception as e:
                _publish(session_id, "reporter", "warning", f"Could not persist finding: {e}")

        # ── 8. Persist report (fresh session) ─────────────────────────────────
        report_md = final_state.get("report_markdown", "")
        if report_md:
            try:
                _persist_report(session_id, report_md, final_state.get("chart_paths", []))
            except Exception as e:
                _publish(session_id, "reporter", "warning", f"Could not persist report: {e}")

        # ── 9. Finalise session (fresh session) ────────────────────────────────
        _finalise_session(session_id, final_state.get("analysis_plan", {}))

        _publish(session_id, "reporter", "completed",
                 f"Analysis complete! {len(final_state.get('findings', []))} findings, "
                 f"{len(final_state.get('chart_paths', []))} charts, report ready.",
                 {"findings_count": len(final_state.get("findings", [])),
                  "chart_count": len(final_state.get("chart_paths", []))})

    except Exception as e:
        _publish(session_id, "orchestrator", "failed", f"Analysis pipeline failed: {str(e)}")
        _fail_session(session_id)

    finally:
        cleanup_temp_files(local_dataset_path or "", charts_dir or "")
