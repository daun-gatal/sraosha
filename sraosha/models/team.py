from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
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
