import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Numeric, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running")
    # running | completed | failed | skipped

    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code_executed: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_cost: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
