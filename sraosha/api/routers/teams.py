import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.models.contract import Contract
from sraosha.models.dq_check import DQCheck
from sraosha.models.team import Team
from sraosha.schemas.team_settings import (
    TeamSettingsCreate,
    TeamSettingsResponse,
    TeamSettingsUpdate,
)

router = APIRouter()


@router.get("", response_model=list[TeamSettingsResponse])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()
    return [TeamSettingsResponse.model_validate(t) for t in teams]


@router.post("", response_model=TeamSettingsResponse, status_code=201)
async def create_team(body: TeamSettingsCreate, db: AsyncSession = Depends(get_db)):
    if body.default_alerting_profile_id:
        from sraosha.models.alerting import AlertingProfile

        ap = await db.get(AlertingProfile, body.default_alerting_profile_id)
        if not ap:
            raise HTTPException(status_code=400, detail="default_alerting_profile_id not found")
    team = Team(
        name=body.name.strip(),
        default_alerting_profile_id=body.default_alerting_profile_id,
    )
    db.add(team)
    try:
        await db.flush()
    except Exception:
        raise HTTPException(status_code=409, detail="Team name already exists") from None
    await db.refresh(team)
    return TeamSettingsResponse.model_validate(team)


@router.get("/{team_id}", response_model=TeamSettingsResponse)
async def get_team(team_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid team ID")
    team = await db.get(Team, uid)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamSettingsResponse.model_validate(team)


@router.patch("/{team_id}", response_model=TeamSettingsResponse)
async def update_team(
    team_id: str, body: TeamSettingsUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        uid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid team ID")
    team = await db.get(Team, uid)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    data = body.model_dump(exclude_unset=True)
    if "default_alerting_profile_id" in data and data["default_alerting_profile_id"]:
        from sraosha.models.alerting import AlertingProfile

        ap = await db.get(AlertingProfile, data["default_alerting_profile_id"])
        if not ap:
            raise HTTPException(status_code=400, detail="default_alerting_profile_id not found")
    for k, v in data.items():
        setattr(team, k, v)
    try:
        await db.flush()
    except Exception:
        raise HTTPException(status_code=409, detail="Team name already exists") from None
    await db.refresh(team)
    return TeamSettingsResponse.model_validate(team)


@router.delete("/{team_id}", status_code=204)
async def delete_team(team_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid team ID")
    team = await db.get(Team, uid)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    c = await db.scalar(
        select(func.count()).select_from(Contract).where(Contract.team_id == uid)
    )
    d = await db.scalar(
        select(func.count()).select_from(DQCheck).where(DQCheck.team_id == uid)
    )
    if (c or 0) > 0 or (d or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail="Team is referenced by contracts or data quality checks",
        )
    await db.delete(team)
