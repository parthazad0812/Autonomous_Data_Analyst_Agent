from pydantic import BaseModel
from datetime import datetime


class SessionOut(BaseModel):
    id: str
    user_id: str
    title: str | None
    status: str
    dataset_filename: str
    dataset_size_bytes: int | None = None
    dataset_rows: int | None
    dataset_columns: int | None
    user_query: str | None
    created_at: datetime
    completed_at: datetime | None
    total_llm_cost: float
    total_llm_tokens: int

    model_config = {"from_attributes": True}


class SessionListOut(BaseModel):
    sessions: list[SessionOut]
    total: int
