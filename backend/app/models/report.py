import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    report_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audience_level: Mapped[str] = mapped_column(String(50), default="balanced")
    # technical | balanced | executive

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
