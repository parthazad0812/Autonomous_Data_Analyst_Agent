from pydantic import BaseModel
from typing import Any


class ColumnMeta(BaseModel):
    name: str
    dtype: str
    col_type: str           # numeric | text | datetime | boolean
    null_count: int
    null_pct: float
    unique_count: int
    # numeric extras (optional)
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    max: float | None = None
    # text extras (optional)
    top_values: dict[str, int] | None = None


class DatasetProfile(BaseModel):
    rows: int
    columns: int
    column_names: list[str]
    columns_meta: list[ColumnMeta]
    sample_rows: list[dict[str, Any]]
    numeric_cols: list[str]
    text_cols: list[str]
    datetime_cols: list[str]
    has_nulls: bool
    memory_mb: float


class UploadResponse(BaseModel):
    session_id: str
    title: str | None
    dataset_filename: str
    dataset_size_bytes: int
    profile: DatasetProfile
    message: str = "Dataset uploaded and profiled successfully"
