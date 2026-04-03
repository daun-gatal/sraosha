from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sraosha.models.base import Base, UUIDType

if TYPE_CHECKING:
    from sraosha.models.alerting import AlertingProfile


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    default_alerting_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("alerting_profiles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    default_alerting_profile: Mapped["AlertingProfile | None"] = relationship(
        "AlertingProfile",
        foreign_keys=[default_alerting_profile_id],
    )


class ComplianceScore(Base):
    __tablename__ = "compliance_scores"
    __table_args__ = (UniqueConstraint("team_id", "period_start", "period_end"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("teams.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    violations_count: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
