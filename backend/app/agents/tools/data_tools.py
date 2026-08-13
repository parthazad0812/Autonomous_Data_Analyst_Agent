"""
Data tools — download dataset from MinIO to a local temp file,
and upload chart PNGs from local temp files back to MinIO.
"""

import os
import uuid
import tempfile
from app.services.minio_service import get_minio_client, ensure_bucket_exists
from app.config import settings


def download_dataset_to_temp(minio_object_name: str) -> str:
    """
    Download a dataset file from MinIO to a local temp file.
    Returns the local file path (caller is responsible for cleanup).
    """
    client = get_minio_client()
    ext = os.path.splitext(minio_object_name)[1] or ".csv"
    tmp_path = os.path.join(tempfile.gettempdir(), f"ada_dataset_{uuid.uuid4().hex}{ext}")
    client.fget_object(settings.minio_bucket, minio_object_name, tmp_path)
    return tmp_path


def upload_chart_to_minio(local_path: str, session_id: str) -> str:
    """
    Upload a chart PNG (or JSON) from local temp path to MinIO.
    Returns the MinIO object name (storage path).
    """
    ensure_bucket_exists()
    client = get_minio_client()
    ext = os.path.splitext(local_path)[1]
    filename = os.path.basename(local_path)
    object_name = f"charts/{session_id}/{filename}"
    content_type = "image/png" if ext == ".png" else "application/json"
    client.fput_object(
        settings.minio_bucket,
        object_name,
        local_path,
        content_type=content_type,
    )
    return object_name


def make_charts_temp_dir(session_id: str) -> str:
    """Create a session-scoped temp directory for chart output files."""
    d = os.path.join(tempfile.gettempdir(), f"ada_charts_{session_id}")
    os.makedirs(d, exist_ok=True)
    return d


def cleanup_temp_files(*paths: str) -> None:
    """Delete temp files/directories, ignoring errors."""
    import shutil
    for p in paths:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.isfile(p):
                os.unlink(p)
        except OSError:
            pass
