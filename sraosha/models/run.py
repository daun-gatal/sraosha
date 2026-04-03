import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sraosha.models.base import Base, UUIDType


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[str] = mapped_column(
        String, ForeignKey("contracts.contract_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    enforcement_mode: Mapped[str] = mapped_column(String, nullable=False)
    checks_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    server: Mapped[str | None] = mapped_column(String, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
