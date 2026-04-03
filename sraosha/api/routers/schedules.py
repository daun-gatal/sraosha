"""REST API endpoints for validation schedules."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.models.contract import Contract
from sraosha.models.dq_check import DQCheck
from sraosha.models.dq_schedule import DQSchedule
from sraosha.models.schedule import ValidationSchedule
from sraosha.models.team import Team
from sraosha.schemas.schedule import (
    ScheduleListItem,
    ScheduleListResponse,
    ScheduleRequest,
    ScheduleResponse,
)

router = APIRouter()

PRESET_SECONDS: dict[str, int] = {
    "hourly": 3600,
    "every_6h": 21600,
    "every_12h": 43200,
    "daily": 86400,
    "weekly": 604800,
}


def _compute_next_run(preset: str, cron_expr: str | None) -> datetime:
    now = datetime.now(timezone.utc)
    if preset == "custom" and cron_expr:
        from croniter import croniter

        cron = croniter(cron_expr, now)
        next_run = cast(datetime, cron.get_next(datetime))
        return next_run.replace(tzinfo=timezone.utc)
    seconds = PRESET_SECONDS.get(preset, 86400)
    return now + timedelta(seconds=seconds)


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    type: str = Query("all", alias="type"),
):
    items: list[ScheduleListItem] = []

    if type in ("all", "contract"):
        query = (
            select(ValidationSchedule, Contract.title, Team.name)
            .join(Contract, Contract.contract_id == ValidationSchedule.contract_id)
            .outerjoin(Team, Contract.team_id == Team.id)
            .order_by(ValidationSchedule.next_run_at.asc())
        )
        result = await db.execute(query)
        for sched, title, owner_team in result.all():
            items.append(
                ScheduleListItem(
                    id=sched.id,
                    schedule_type="contract",
                    contract_id=sched.contract_id,
                    contract_title=title,
                    owner_team=owner_team,
                    is_enabled=sched.is_enabled,
                    interval_preset=sched.interval_preset,
                    cron_expression=sched.cron_expression,
                    next_run_at=sched.next_run_at,
                    last_run_at=sched.last_run_at,
                )
            )

    if type in ("all", "data_quality"):
        dq_query = (
            select(DQSchedule, DQCheck.name)
            .join(DQCheck, DQCheck.id == DQSchedule.dq_check_id)
            .order_by(DQSchedule.next_run_at.asc())
        )
        dq_result = await db.execute(dq_query)
        for sched, check_name in dq_result.all():
            items.append(
                ScheduleListItem(
                    id=sched.id,
                    schedule_type="data_quality",
                    dq_check_id=sched.dq_check_id,
                    dq_check_name=check_name,
                    is_enabled=sched.is_enabled,
                    interval_preset=sched.interval_preset,
                    cron_expression=sched.cron_expression,
                    next_run_at=sched.next_run_at,
                    last_run_at=sched.last_run_at,
                )
            )

    items.sort(key=lambda s: s.next_run_at)
    return ScheduleListResponse(items=items, total=len(items))


@router.post("/contracts/{contract_id}/schedule", response_model=ScheduleResponse)
async def upsert_schedule(
    contract_id: str,
    body: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
):
    contract_result = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    result = await db.execute(
        select(ValidationSchedule).where(ValidationSchedule.contract_id == contract_id)
    )
    schedule = result.scalar_one_or_none()

    next_run = _compute_next_run(body.interval_preset, body.cron_expression)

    if schedule:
        schedule.interval_preset = body.interval_preset
        schedule.cron_expression = body.cron_expression
        schedule.is_enabled = body.is_enabled
        schedule.next_run_at = next_run
        schedule.updated_at = datetime.now(timezone.utc)
    else:
        schedule = ValidationSchedule(
            contract_id=contract_id,
            interval_preset=body.interval_preset,
            cron_expression=body.cron_expression,
            is_enabled=body.is_enabled,
            next_run_at=next_run,
        )
        db.add(schedule)

    await db.flush()
    await db.refresh(schedule)
    return ScheduleResponse.model_validate(schedule)


@router.delete("/contracts/{contract_id}/schedule")
async def delete_schedule(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ValidationSchedule).where(ValidationSchedule.contract_id == contract_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    return {"detail": "Schedule deleted"}


@router.post("/dq/{dq_check_id}/schedule")
async def upsert_dq_schedule(
    dq_check_id: uuid_mod.UUID,
    body: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
):
    check_result = await db.execute(select(DQCheck).where(DQCheck.id == dq_check_id))
    if not check_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="DQ check not found")

    result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == dq_check_id))
    schedule = result.scalar_one_or_none()
    next_run = _compute_next_run(body.interval_preset, body.cron_expression)

    if schedule:
        schedule.interval_preset = body.interval_preset
        schedule.cron_expression = body.cron_expression
        schedule.is_enabled = body.is_enabled
        schedule.next_run_at = next_run
        schedule.updated_at = datetime.now(timezone.utc)
    else:
        schedule = DQSchedule(
            dq_check_id=dq_check_id,
            interval_preset=body.interval_preset,
            cron_expression=body.cron_expression,
            is_enabled=body.is_enabled,
            next_run_at=next_run,
        )
        db.add(schedule)

    await db.flush()
    await db.refresh(schedule)
    return {
        "id": str(schedule.id),
        "dq_check_id": str(dq_check_id),
        "next_run_at": str(schedule.next_run_at),
    }


@router.delete("/dq/{dq_check_id}/schedule")
async def delete_dq_schedule(
    dq_check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == dq_check_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    return {"detail": "Schedule deleted"}
