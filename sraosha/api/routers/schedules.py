"""REST API endpoints for validation schedules."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.models.contract import Contract
from sraosha.models.dq_check import DQCheck
from sraosha.models.dq_run import DQCheckRun
from sraosha.models.dq_schedule import DQSchedule
from sraosha.models.run import ValidationRun
from sraosha.models.schedule import ValidationSchedule
from sraosha.models.team import Team
from sraosha.schemas.schedule import (
    ScheduleListItem,
    ScheduleListResponse,
    ScheduleRequest,
    ScheduleResponse,
)
from sraosha.services.schedules import compute_next_schedule_run

router = APIRouter()


async def _latest_validation_run_ids(
    db: AsyncSession, contract_ids: list[str]
) -> dict[str, uuid_mod.UUID]:
    if not contract_ids:
        return {}
    sub = (
        select(ValidationRun.contract_id, func.max(ValidationRun.run_at).label("mx"))
        .where(ValidationRun.contract_id.in_(contract_ids))
        .group_by(ValidationRun.contract_id)
    ).subquery()
    result = await db.execute(
        select(ValidationRun.contract_id, ValidationRun.id)
        .select_from(ValidationRun)
        .join(
            sub,
            and_(
                ValidationRun.contract_id == sub.c.contract_id,
                ValidationRun.run_at == sub.c.mx,
            ),
        )
    )
    by_contract: dict[str, list[uuid_mod.UUID]] = {}
    for cid, rid in result.all():
        by_contract.setdefault(cid, []).append(rid)
    # PostgreSQL has no max(uuid); break ties in Python.
    return {cid: max(rids) for cid, rids in by_contract.items()}


async def _latest_dq_run_ids(
    db: AsyncSession, dq_check_ids: list[uuid_mod.UUID]
) -> dict[uuid_mod.UUID, uuid_mod.UUID]:
    if not dq_check_ids:
        return {}
    sub = (
        select(DQCheckRun.dq_check_id, func.max(DQCheckRun.run_at).label("mx"))
        .where(DQCheckRun.dq_check_id.in_(dq_check_ids))
        .group_by(DQCheckRun.dq_check_id)
    ).subquery()
    result = await db.execute(
        select(DQCheckRun.dq_check_id, DQCheckRun.id)
        .select_from(DQCheckRun)
        .join(
            sub,
            and_(
                DQCheckRun.dq_check_id == sub.c.dq_check_id,
                DQCheckRun.run_at == sub.c.mx,
            ),
        )
    )
    by_check: dict[uuid_mod.UUID, list[uuid_mod.UUID]] = {}
    for qid, rid in result.all():
        by_check.setdefault(qid, []).append(rid)
    return {qid: max(rids) for qid, rids in by_check.items()}


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

    contract_ids = list(
        {i.contract_id for i in items if i.schedule_type == "contract" and i.contract_id}
    )
    dq_ids = list(
        {i.dq_check_id for i in items if i.schedule_type == "data_quality" and i.dq_check_id}
    )
    val_by_contract = await _latest_validation_run_ids(db, contract_ids)
    dq_by_check = await _latest_dq_run_ids(db, dq_ids)

    def _with_last_run_id(row: ScheduleListItem) -> ScheduleListItem:
        if row.schedule_type == "contract" and row.contract_id:
            rid = val_by_contract.get(row.contract_id)
            return row.model_copy(update={"last_run_id": rid})
        if row.schedule_type == "data_quality" and row.dq_check_id:
            rid = dq_by_check.get(row.dq_check_id)
            return row.model_copy(update={"last_run_id": rid})
        return row

    items = [_with_last_run_id(i) for i in items]

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

    next_run = compute_next_schedule_run(body.interval_preset, body.cron_expression)

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
    next_run = compute_next_schedule_run(body.interval_preset, body.cron_expression)

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
