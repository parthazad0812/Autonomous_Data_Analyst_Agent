"""
Upload Service — handles file validation, pandas profiling, and MinIO storage.
Supports: CSV, XLSX, JSON, Parquet
"""

import io
import uuid
import os
from typing import Any

import numpy as np
import pandas as pd

from fastapi import UploadFile, HTTPException, status
from app.config import settings
from app.services.minio_service import upload_file_to_minio

# ── Allowed file types ─────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/json",
    "application/octet-stream",  # Parquet files often have this
    "application/x-parquet",
}
MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


def _get_extension(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


def validate_file(file: UploadFile, raw_bytes: bytes) -> None:
    """Raise HTTPException if the file fails any validation check."""
    # 1. Size
    if len(raw_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed: {settings.max_upload_size_mb} MB",
        )

    # 2. Extension
    ext = _get_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 3. Empty file
    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file is empty.",
        )


def load_dataframe(raw_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Load bytes into a pandas DataFrame.
    Raises HTTPException if the file cannot be parsed.
    """
    ext = _get_extension(filename)
    try:
        buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            df = pd.read_csv(buf, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(buf, engine="openpyxl")
        elif ext == ".json":
            df = pd.read_json(buf)
        elif ext == ".parquet":
            df = pd.read_parquet(buf)
        else:
            raise ValueError(f"Unsupported extension: {ext}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse file: {str(e)}",
        ) from e

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The dataset is empty (zero rows).",
        )
    return df


def _safe_value(val: Any) -> Any:
    """Convert numpy/pandas scalars to JSON-safe Python types."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return None if np.isnan(val) else float(val)
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return None
    return val


def profile_dataframe(df: pd.DataFrame) -> dict:
    """
    Generate a structured profile of the dataframe:
    - shape, dtypes, null counts, numeric stats
    - sample rows (first 50, serialised to JSON-safe format)
    """
    rows, cols = df.shape

    # ── Column metadata ──────────────────────────────────────────────────────
    columns_meta = []
    for col in df.columns:
        col_series = df[col]
        dtype = str(col_series.dtype)

        # Categorise the column (order matters: bool before numeric)
        if pd.api.types.is_bool_dtype(col_series):
            col_type = "boolean"
        elif pd.api.types.is_datetime64_any_dtype(col_series):
            col_type = "datetime"
        elif pd.api.types.is_numeric_dtype(col_series):
            # Check if it looks like a boolean stored as 0/1
            unique_vals = col_series.dropna().unique()
            if set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                col_type = "boolean"
            else:
                col_type = "numeric"
        else:
            # Check for string booleans
            lower_unique = set(str(v).lower() for v in col_series.dropna().unique())
            if lower_unique.issubset({"true", "false", "yes", "no", "1", "0"}):
                col_type = "boolean"
            else:
                col_type = "text"


        null_count = int(col_series.isna().sum())
        null_pct = round(null_count / rows * 100, 2) if rows > 0 else 0
        unique_count = int(col_series.nunique())

        meta: dict = {
            "name": col,
            "dtype": dtype,
            "col_type": col_type,
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_count": unique_count,
        }

        # Add numeric stats for numeric columns
        if col_type == "numeric":
            desc = col_series.describe()
            meta.update({
                "mean": _safe_value(desc.get("mean")),
                "std": _safe_value(desc.get("std")),
                "min": _safe_value(desc.get("min")),
                "p25": _safe_value(desc.get("25%")),
                "p50": _safe_value(desc.get("50%")),
                "p75": _safe_value(desc.get("75%")),
                "max": _safe_value(desc.get("max")),
            })
        elif col_type == "text":
            # Top 5 most common values
            top_values = col_series.value_counts().head(5).to_dict()
            meta["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        columns_meta.append(meta)

    # ── Sample rows (first 50) ───────────────────────────────────────────────
    sample_df = df.head(50).copy()

    # Convert datetime columns to strings for JSON serialisation
    for col in sample_df.select_dtypes(include=["datetime64"]).columns:
        sample_df[col] = sample_df[col].astype(str)

    # Replace NaN/inf with None
    sample_df = sample_df.where(pd.notna(sample_df), None)
    sample_records = sample_df.to_dict(orient="records")

    # JSON-safe all values
    safe_records = []
    for record in sample_records:
        safe_records.append({k: _safe_value(v) for k, v in record.items()})

    return {
        "rows": rows,
        "columns": cols,
        "column_names": list(df.columns),
        "columns_meta": columns_meta,
        "sample_rows": safe_records,
        "numeric_cols": [c["name"] for c in columns_meta if c["col_type"] == "numeric"],
        "text_cols": [c["name"] for c in columns_meta if c["col_type"] == "text"],
        "datetime_cols": [c["name"] for c in columns_meta if c["col_type"] == "datetime"],
        "has_nulls": any(c["null_count"] > 0 for c in columns_meta),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
    }


def store_dataset(raw_bytes: bytes, session_id: str, filename: str) -> str:
    """
    Upload the raw file to MinIO.
    Returns the object_name (storage path).
    """
    ext = _get_extension(filename)
    object_name = f"datasets/{session_id}/{uuid.uuid4().hex}{ext}"
    upload_file_to_minio(object_name, raw_bytes)
    return object_name
