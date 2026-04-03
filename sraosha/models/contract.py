import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sraosha.models.alerting import AlertingProfile
from sraosha.models.base import Base, UUIDType
from sraosha.models.team import Team


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    alerting_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("alerting_profiles.id", ondelete="SET NULL"), nullable=True
    )
    raw_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    enforcement_mode: Mapped[str] = mapped_column(String, nullable=False, default="block")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    team: Mapped[Team | None] = relationship("Team", foreign_keys=[team_id])
    alerting_profile: Mapped[AlertingProfile | None] = relationship(
        "AlertingProfile", foreign_keys=[alerting_profile_id]
    )

    @property
    def owner_team(self) -> str | None:
        """Denormalized name for API/YAML compatibility."""
        return self.team.name if self.team is not None else None
