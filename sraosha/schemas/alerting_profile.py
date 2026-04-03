import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from sraosha.alerting.channel_types import CHANNEL_EMAIL, CHANNEL_SLACK, CHANNEL_WEBHOOK


class AlertingChannelCreate(BaseModel):
    channel_type: str
    config: dict[str, Any]
    is_enabled: bool = True
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_config(self):
        ct = self.channel_type
        if ct not in (CHANNEL_SLACK, CHANNEL_EMAIL, CHANNEL_WEBHOOK):
            raise ValueError("channel_type must be slack, email, or webhook")
        cfg = self.config
        if ct == CHANNEL_SLACK:
            if not cfg.get("channel") and not cfg.get("slack_channel"):
                raise ValueError("slack config requires 'channel' or 'slack_channel'")
        elif ct == CHANNEL_EMAIL:
            if not cfg.get("to") and not cfg.get("email"):
                raise ValueError("email config requires 'to' or 'email'")
        elif ct == CHANNEL_WEBHOOK:
            if not cfg.get("url"):
                raise ValueError("webhook config requires 'url'")
        return self


class AlertingChannelResponse(BaseModel):
    id: uuid.UUID
    alerting_profile_id: uuid.UUID
    channel_type: str
    config: dict[str, Any]
    is_enabled: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertingChannelUpdate(BaseModel):
    channel_type: str | None = None
    config: dict[str, Any] | None = None
    is_enabled: bool | None = None
    sort_order: int | None = None


class AlertingProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    channels: list[AlertingChannelCreate] = Field(default_factory=list)


class AlertingProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class AlertingProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    channels: list[AlertingChannelResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertingProfileListResponse(BaseModel):
    items: list[AlertingProfileResponse]
    total: int
