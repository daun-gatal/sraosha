import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    slack_channel: str | None
    email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamWithScoreResponse(TeamResponse):
    current_score: float | None = None
    contracts_owned: int = 0
    violations_30d: int = 0


class ComplianceScoreResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    score: float
    total_runs: int
    passed_runs: int
    violations_count: int
    period_start: date
    period_end: date
    computed_at: datetime

    model_config = {"from_attributes": True}


class TeamDetailResponse(TeamResponse):
    scores: list[ComplianceScoreResponse] = []


class LeaderboardEntry(BaseModel):
    rank: int
    team_name: str
    team_id: uuid.UUID
    score: float
    contracts_owned: int
    violations_30d: int


class LeaderboardResponse(BaseModel):
    items: list[LeaderboardEntry]


class ContractSlaResponse(BaseModel):
    contract_id: str
    scores: list[ComplianceScoreResponse]
