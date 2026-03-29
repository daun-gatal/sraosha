import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sraosha.models.base import Base, UUIDType


class DriftMetric(Base):
    __tablename__ = "drift_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[str] = mapped_column(
        String, ForeignKey("contracts.contract_id"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("validation_runs.id"), nullable=True
    )
    metric_type: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str | None] = mapped_column(String, nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    warning_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    breach_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_warning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class DriftBaseline(Base):
    __tablename__ = "drift_baselines"
    __table_args__ = (
        UniqueConstraint("contract_id", "metric_type", "table_name", "column_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[str] = mapped_column(
        String, ForeignKey("contracts.contract_id"), nullable=False
    )
    metric_type: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str | None] = mapped_column(String, nullable=True)
    mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    std_dev: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_trending_to_breach: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_breach_in_runs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
