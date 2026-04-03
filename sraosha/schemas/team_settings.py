import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TeamSettingsCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default_alerting_profile_id: uuid.UUID | None = None


class TeamSettingsUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    default_alerting_profile_id: uuid.UUID | None = None


class TeamSettingsResponse(BaseModel):
    id: uuid.UUID
    name: str
    default_alerting_profile_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
