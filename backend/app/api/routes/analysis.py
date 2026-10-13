"""
Analysis API routes — trigger and read analysis results.

POST /analysis/{session_id}/start   — enqueue background analysis
GET  /analysis/{session_id}/status  — current status
GET  /analysis/{session_id}/steps   — all agent step records
GET  /analysis/{session_id}/findings — all findings
GET  /analysis/{session_id}/report  — markdown report
GET  /analysis/{session_id}/charts  — presigned MinIO URLs for charts
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any
from datetime import datetime
import io

from app.db.database import get_db
from app.models.user import User
from app.models.session import AnalysisSession
from app.models.step import AgentStep
from app.models.finding import Finding
from app.models.report import Report
from app.api.dependencies import get_current_user
from app.services.analysis_service import run_analysis
from app.services.report_service import generate_pdf
from app.services.minio_service import get_presigned_url, list_session_charts
from app.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class StartAnalysisResponse(BaseModel):
    session_id: str
    status: str
    message: str


class StepOut(BaseModel):
    id: str
    agent_name: str
    step_index: int
    status: str
    code_executed: str | None
    code_output: str | None
    error_message: str | None
    duration_seconds: float | None
    output_data: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingOut(BaseModel):
    id: str
    finding_type: str | None
    title: str
    description: str | None
    evidence: dict | None
    confidence: str | None
    hypothesis: str | None
    visualization_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: str
    session_id: str
    report_markdown: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChartURL(BaseModel):
    path: str
    url: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_session_or_404(
    session_id: str, db: Session, current_user: User
) -> AnalysisSession:
    session = (
        db.query(AnalysisSession)
        .filter(
            AnalysisSession.id == session_id,
            AnalysisSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _session_charts(session_id: str, db: Session) -> tuple[list[str], dict[str, str]]:
    """
    Every chart for a session: paths linked from visualization findings plus every PNG
    actually stored in MinIO (charts whose finding is missing or lacks a "charts/" path
    would otherwise never reach the UI or the PDF). Returns (paths, {path: title}).
    """
    viz_findings = (
        db.query(Finding)
        .filter(Finding.session_id == session_id, Finding.finding_type == "visualization")
        .all()
    )
    titles: dict[str, str] = {}
    titles_by_stem: dict[str, str] = {}
    for f in viz_findings:
        path = f.visualization_path or ""
        if path.startswith("charts/"):
            titles[path] = f.title
        elif path:  # legacy findings stored just the chart id, e.g. "V001"
            titles_by_stem[path.rsplit("/", 1)[-1].rsplit(".", 1)[0]] = f.title

    paths = list(titles)
    try:
        stored = list_session_charts(session_id)
    except Exception as exc:
        log.warning("Could not list charts in MinIO", session_id=session_id, error=str(exc))
        stored = []
    for p in stored:
        if p not in titles:
            paths.append(p)
            stem = p.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            titles[p] = titles_by_stem.get(stem, stem)
    return paths, titles


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/{session_id}/start", response_model=StartAnalysisResponse)
def start_analysis(
    request: Request,
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger the multi-agent analysis pipeline for a session.
    The pipeline runs as a FastAPI BackgroundTask.
    Connect to ws://localhost:8000/ws/analysis/{session_id} for live updates.
    """
    session = _get_session_or_404(session_id, db, current_user)

    if session.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already running for this session",
        )
    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis has already completed. Create a new session to re-run.",
        )
    if not session.dataset_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No dataset found in this session. Upload a file first.",
        )

    # Mark as running immediately so the UI can react
    session.status = "running"
    db.commit()

    log.info(
        "Analysis pipeline started",
        session_id=session_id,
        user_id=str(current_user.id),
        dataset=session.dataset_filename,
    )

    # Run analysis in the background
    background_tasks.add_task(run_analysis, session_id)

    return StartAnalysisResponse(
        session_id=session_id,
        status="running",
        message="Analysis pipeline started. Connect to WebSocket for live updates.",
    )


@router.get("/{session_id}/status")
def get_analysis_status(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current status and summary of an analysis session."""
    session = _get_session_or_404(session_id, db, current_user)
    steps_count = db.query(AgentStep).filter(AgentStep.session_id == session_id).count()
    findings_count = db.query(Finding).filter(Finding.session_id == session_id).count()
    has_report = db.query(Report).filter(Report.session_id == session_id).first() is not None

    return {
        "session_id": session_id,
        "status": session.status,
        "dataset_filename": session.dataset_filename,
        "steps_completed": steps_count,
        "findings_count": findings_count,
        "has_report": has_report,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
    }


@router.get("/{session_id}/steps", response_model=list[StepOut])
def get_steps(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all agent step records for a session in execution order."""
    _get_session_or_404(session_id, db, current_user)
    steps = (
        db.query(AgentStep)
        .filter(AgentStep.session_id == session_id)
        .order_by(AgentStep.step_index)
        .all()
    )
    return steps


@router.get("/{session_id}/findings", response_model=list[FindingOut])
def get_findings(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all findings for a session."""
    _get_session_or_404(session_id, db, current_user)
    findings = (
        db.query(Finding)
        .filter(Finding.session_id == session_id)
        .order_by(Finding.created_at)
        .all()
    )
    return findings


@router.get("/{session_id}/report", response_model=ReportOut)
def get_report(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the generated Markdown report for a session."""
    _get_session_or_404(session_id, db, current_user)
    report = db.query(Report).filter(Report.session_id == session_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet generated. Run the analysis first.",
        )
    return report


@router.get("/{session_id}/charts", response_model=list[ChartURL])
def get_chart_urls(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return presigned MinIO URLs for all charts generated for this session."""
    _get_session_or_404(session_id, db, current_user)

    paths, _ = _session_charts(session_id, db)
    chart_urls = []
    for path in paths:
        try:
            url = get_presigned_url(path, expires_hours=2)
            chart_urls.append(ChartURL(path=path, url=url))
        except Exception:
            pass

    return chart_urls


@router.get("/{session_id}/report/download")
def download_report_markdown(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the Markdown report as a .md file attachment.
    GET /analysis/{session_id}/report/download
    """
    _get_session_or_404(session_id, db, current_user)
    report = db.query(Report).filter(Report.session_id == session_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet generated. Run the analysis first.",
        )
    session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
    stem = (session.dataset_filename or "report").rsplit(".", 1)[0]
    filename = f"{stem}_analysis_report.md"

    content = report.report_markdown.encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/report/pdf")
def download_report_pdf(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate and download the report as a styled PDF.
    GET /analysis/{session_id}/report/pdf
    """
    _get_session_or_404(session_id, db, current_user)
    report = db.query(Report).filter(Report.session_id == session_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet generated. Run the analysis first.",
        )

    session = db.query(AnalysisSession).filter(AnalysisSession.id == session_id).first()
    findings_count = db.query(Finding).filter(Finding.session_id == session_id).count()

    # Every chart for the session: linked from findings and/or stored in MinIO
    chart_paths, chart_titles = _session_charts(session_id, db)

    stem = (session.dataset_filename or "report").rsplit(".", 1)[0]
    title = session.title or f"{session.dataset_filename} Analysis Report"
    pdf_filename = f"{stem}_analysis_report.pdf"

    try:
        pdf_bytes = generate_pdf(
            markdown_text=report.report_markdown,
            title=title,
            filename=session.dataset_filename or "dataset",
            findings_count=findings_count,
            chart_paths=chart_paths,
            chart_titles=chart_titles,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(exc)}",
        )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'},
    )
