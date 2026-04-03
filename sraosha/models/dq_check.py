import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sraosha.models.alerting import AlertingProfile
from sraosha.models.base import Base, JSONColumnType, UUIDType
from sraosha.models.team import Team


class DQCheck(Base):
    __tablename__ = "dq_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("connections.id"), nullable=False,
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    alerting_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("alerting_profiles.id", ondelete="SET NULL"), nullable=True
    )
    data_source_name: Mapped[str] = mapped_column(String, nullable=False)
    sodacl_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    tables: Mapped[list | None] = mapped_column(JSONColumnType, nullable=True, default=list)
    check_categories: Mapped[list | None] = mapped_column(
        JSONColumnType, nullable=True, default=list
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tags: Mapped[list | None] = mapped_column(JSONColumnType, nullable=True, default=list)
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
        return self.team.name if self.team is not None else None
