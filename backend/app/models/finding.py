import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    agent_step_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_steps.id"), nullable=True
    )
    finding_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # statistical | visual | anomaly | correlation | hypothesis
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # high | medium | low
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    visualization_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
