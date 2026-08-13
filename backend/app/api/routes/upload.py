import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.session import AnalysisSession
from app.api.dependencies import get_current_user
from app.schemas.session import SessionOut, SessionListOut
from app.schemas.analysis import UploadResponse, DatasetProfile, ColumnMeta
from app.services import upload_service
from app.services.minio_service import delete_file_from_minio

router = APIRouter(prefix="/upload", tags=["Upload & Sessions"])

# ── POST /upload ──────────────────────────────────────────────────────────────
@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV, XLSX, JSON or Parquet file"),
    query: str = Form(default="", description="Optional natural-language analysis query"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a dataset file. Returns a session ID and a full data profile.
    The dataset is stored in MinIO and a session record is created in PostgreSQL.
    """
    # 1. Read bytes
    raw_bytes = await file.read()

    # 2. Validate
    upload_service.validate_file(file, raw_bytes)

    # 3. Parse into DataFrame
    df = upload_service.load_dataframe(raw_bytes, file.filename or "upload")

    # 4. Profile the dataset
    profile_dict = upload_service.profile_dataframe(df)

    # 5. Create a session record first so we have the ID for storage
    session_id = str(uuid.uuid4())
    title = query[:100] if query else f"Analysis of {file.filename}"

    db_session = AnalysisSession(
        id=session_id,
        user_id=current_user.id,
        title=title,
        status="pending",
        dataset_filename=file.filename or "upload",
        dataset_size_bytes=len(raw_bytes),
        dataset_rows=profile_dict["rows"],
        dataset_columns=profile_dict["columns"],
        user_query=query or None,
        analysis_plan=None,
    )
    db.add(db_session)
    db.commit()

    # 6. Store file in MinIO (after commit so we have session_id)
    try:
        object_name = upload_service.store_dataset(raw_bytes, session_id, file.filename or "upload")
        db_session.dataset_path = object_name
        db.commit()
    except Exception as e:
        # Roll back: delete session if MinIO upload fails
        db.delete(db_session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File storage failed: {str(e)}",
        ) from e

    # 7. Build response
    columns_meta = [ColumnMeta(**c) for c in profile_dict["columns_meta"]]
    profile = DatasetProfile(
        **{k: v for k, v in profile_dict.items() if k != "columns_meta"},
        columns_meta=columns_meta,
    )

    return UploadResponse(
        session_id=session_id,
        title=title,
        dataset_filename=file.filename or "upload",
        dataset_size_bytes=len(raw_bytes),
        profile=profile,
    )


# ── GET /sessions ──────────────────────────────────────────────────────────────
@router.get("/sessions", response_model=SessionListOut, tags=["Sessions"])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all analysis sessions for the authenticated user (newest first)."""
    sessions = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.user_id == current_user.id)
        .order_by(AnalysisSession.created_at.desc())
        .all()
    )
    return SessionListOut(
        sessions=[SessionOut.model_validate(s) for s in sessions],
        total=len(sessions),
    )


# ── GET /sessions/{id} ────────────────────────────────────────────────────────
@router.get("/sessions/{session_id}", response_model=SessionOut, tags=["Sessions"])
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single session by ID (must belong to authenticated user)."""
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
    return SessionOut.model_validate(session)


# ── DELETE /sessions/{id} ─────────────────────────────────────────────────────
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Sessions"])
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a session and its associated file from MinIO."""
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

    # Remove file from MinIO
    if session.dataset_path:
        delete_file_from_minio(session.dataset_path)

    db.delete(session)
    db.commit()
