import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sraosha.models.base import Base, JSONColumnType, UUIDType


class DQCheckRun(Base):
    __tablename__ = "dq_check_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    dq_check_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("dq_checks.id"), nullable=False,
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    checks_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_warned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results_json: Mapped[dict | None] = mapped_column(JSONColumnType, nullable=True)
    diagnostics_json: Mapped[dict | None] = mapped_column(JSONColumnType, nullable=True)
    run_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
