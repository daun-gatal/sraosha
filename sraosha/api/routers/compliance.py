import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sraosha.alerting.profile_contact import slack_and_email_from_profile
from sraosha.api.deps import get_db
from sraosha.models.alerting import AlertingProfile
from sraosha.models.contract import Contract
from sraosha.models.team import ComplianceScore, Team
from sraosha.schemas.compliance import (
    ComplianceScoreResponse,
    ContractSlaResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    TeamDetailResponse,
    TeamWithScoreResponse,
)

router = APIRouter()


@router.get("/teams", response_model=list[TeamWithScoreResponse])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Team)
        .options(
            selectinload(Team.default_alerting_profile).selectinload(AlertingProfile.channels)
        )
        .order_by(Team.name)
    )
    teams = result.scalars().unique().all()

    responses = []
    for team in teams:
        score_result = await db.execute(
            select(ComplianceScore)
            .where(ComplianceScore.team_id == team.id)
            .order_by(ComplianceScore.period_end.desc())
            .limit(1)
        )
        latest_score = score_result.scalar_one_or_none()

        contracts_result = await db.execute(
            select(func.count()).select_from(Contract).where(Contract.team_id == team.id)
        )
        contracts_owned = contracts_result.scalar() or 0

        slack_ch, email = slack_and_email_from_profile(team.default_alerting_profile)

        responses.append(
            TeamWithScoreResponse(
                id=team.id,
                name=team.name,
                slack_channel=slack_ch,
                email=email,
                created_at=team.created_at,
                current_score=latest_score.score if latest_score else None,
                contracts_owned=contracts_owned,
                violations_30d=latest_score.violations_count if latest_score else 0,
            )
        )
    return responses


@router.get("/teams/{team_id}", response_model=TeamDetailResponse)
async def get_team(team_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid_mod.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid team ID")

    result = await db.execute(
        select(Team)
        .where(Team.id == uid)
        .options(
            selectinload(Team.default_alerting_profile).selectinload(AlertingProfile.channels)
        )
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    scores_result = await db.execute(
        select(ComplianceScore)
        .where(ComplianceScore.team_id == team.id)
        .order_by(ComplianceScore.period_end.desc())
    )
    scores = scores_result.scalars().all()

    slack_ch, email = slack_and_email_from_profile(team.default_alerting_profile)

    return TeamDetailResponse(
        id=team.id,
        name=team.name,
        slack_channel=slack_ch,
        email=email,
        created_at=team.created_at,
        scores=[ComplianceScoreResponse.model_validate(s) for s in scores],
    )


@router.get("/contracts/{contract_id}/sla", response_model=ContractSlaResponse)
async def contract_sla(contract_id: str, db: AsyncSession = Depends(get_db)):
    contract_result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    contract = contract_result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.team_id:
        team_result = await db.execute(select(Team).where(Team.id == contract.team_id))
        team = team_result.scalar_one_or_none()
        if team:
            scores_result = await db.execute(
                select(ComplianceScore)
                .where(ComplianceScore.team_id == team.id)
                .order_by(ComplianceScore.period_end.desc())
            )
            scores = scores_result.scalars().all()
            return ContractSlaResponse(
                contract_id=contract_id,
                scores=[ComplianceScoreResponse.model_validate(s) for s in scores],
            )

    return ContractSlaResponse(contract_id=contract_id, scores=[])


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()

    entries: list[tuple[float, LeaderboardEntry]] = []
    for team in teams:
        score_result = await db.execute(
            select(ComplianceScore)
            .where(ComplianceScore.team_id == team.id)
            .order_by(ComplianceScore.period_end.desc())
            .limit(1)
        )
        latest = score_result.scalar_one_or_none()
        if latest is None:
            continue

        contracts_result = await db.execute(
            select(func.count()).select_from(Contract).where(Contract.team_id == team.id)
        )
        contracts_owned = contracts_result.scalar() or 0

        entries.append(
            (
                latest.score,
                LeaderboardEntry(
                    rank=0,
                    team_name=team.name,
                    team_id=team.id,
                    score=latest.score,
                    contracts_owned=contracts_owned,
                    violations_30d=latest.violations_count,
                ),
            )
        )

    entries.sort(key=lambda x: x[0], reverse=True)
    items = []
    for i, (_, entry) in enumerate(entries, 1):
        entry.rank = i
        items.append(entry)

    return LeaderboardResponse(items=items)
