import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sraosha.models.base import Base, JSONColumnType, UUIDType


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    server_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    host: Mapped[str | None] = mapped_column(String, nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database: Mapped[str | None] = mapped_column(String, nullable=True)
    schema_name: Mapped[str | None] = mapped_column(String, nullable=True)
    account: Mapped[str | None] = mapped_column(String, nullable=True)
    warehouse: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    catalog: Mapped[str | None] = mapped_column(String, nullable=True)
    http_path: Mapped[str | None] = mapped_column(String, nullable=True)
    project: Mapped[str | None] = mapped_column(String, nullable=True)
    dataset: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_account_json_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_params: Mapped[dict | None] = mapped_column(JSONColumnType, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
