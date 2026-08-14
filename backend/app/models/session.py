import uuid
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Text, DateTime, ForeignKey, Numeric, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending | running | completed | failed

    dataset_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    dataset_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # MinIO path
    dataset_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    dataset_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_columns: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    total_llm_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    total_llm_tokens: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<AnalysisSession id={self.id} status={self.status}>"
