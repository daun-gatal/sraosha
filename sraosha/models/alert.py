import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sraosha.models.base import Base, UUIDType


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contracts.contract_id"), nullable=True
    )
    dq_check_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("dq_checks.id", ondelete="SET NULL"), nullable=True
    )
    alerting_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("alerting_profiles.id", ondelete="SET NULL"), nullable=True
    )
    alerting_profile_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("alerting_profile_channels.id", ondelete="SET NULL"), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    channel_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
