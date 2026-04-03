from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from sraosha.api.deps import get_db
from sraosha.models.alerting import AlertingProfile
from sraosha.models.connection import Connection
from sraosha.models.dq_check import DQCheck
from sraosha.models.dq_run import DQCheckRun
from sraosha.models.dq_schedule import DQSchedule
from sraosha.models.team import Team
from sraosha.schemas.data_quality import (
    DQCheckCreate,
    DQCheckListResponse,
    DQCheckResponse,
    DQCheckUpdate,
    DQRunListResponse,
    DQRunResponse,
    DQSummaryResponse,
)
from sraosha.tasks.dq_scan import run_dq_check

router = APIRouter()


class DQCheckDetailPayload(BaseModel):
    check: DQCheckResponse
    recent_runs: list[DQRunResponse]


def _list_stmt():
    run_count_sub = (
        select(
            DQCheckRun.dq_check_id.label("cid"),
            func.count(DQCheckRun.id).label("cnt"),
        )
        .group_by(DQCheckRun.dq_check_id)
        .subquery()
    )
    latest_sub = (
        select(
            DQCheckRun.dq_check_id.label("cid"),
            func.max(DQCheckRun.run_at).label("latest_at"),
        )
        .group_by(DQCheckRun.dq_check_id)
        .subquery()
    )
    latest_run = aliased(DQCheckRun)
    return (
        select(DQCheck, latest_run, run_count_sub.c.cnt)
        .outerjoin(latest_sub, latest_sub.c.cid == DQCheck.id)
        .outerjoin(
            latest_run,
            (latest_run.dq_check_id == DQCheck.id)
            & (latest_run.run_at == latest_sub.c.latest_at),
        )
        .outerjoin(run_count_sub, run_count_sub.c.cid == DQCheck.id)
        .options(selectinload(DQCheck.team), selectinload(DQCheck.alerting_profile))
        .order_by(DQCheck.name.asc())
    )


def _to_check_response(
    check: DQCheck,
    latest: DQCheckRun | None,
    run_count: int | None,
) -> DQCheckResponse:
    rc = int(run_count or 0)
    latest_status = latest.status if latest else None
    pass_rate: float | None = None
    if latest and latest.checks_total > 0:
        pass_rate = latest.checks_passed / latest.checks_total
    return DQCheckResponse(
        id=check.id,
        name=check.name,
        description=check.description,
        connection_id=check.connection_id,
        team_id=check.team_id,
        alerting_profile_id=check.alerting_profile_id,
        owner_team=check.owner_team,
        data_source_name=check.data_source_name,
        sodacl_yaml=check.sodacl_yaml,
        tables=list(check.tables or []),
        check_categories=list(check.check_categories or []),
        is_enabled=check.is_enabled,
        tags=list(check.tags or []),
        created_at=check.created_at,
        updated_at=check.updated_at,
        latest_status=latest_status,
        pass_rate=pass_rate,
        run_count=rc,
    )


def _bucket_latest(status: str | None) -> str:
    if status is None:
        return "error"
    s = status.lower()
    if s in ("passed", "pass", "success", "ok"):
        return "healthy"
    if "warn" in s:
        return "warning"
    if s in ("failed", "fail"):
        return "failed"
    if s in ("error", "errored"):
        return "error"
    return "error"


@router.get("", response_model=DQCheckListResponse)
async def list_dq_checks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(_list_stmt())
    seen: dict[uuid.UUID, DQCheckResponse] = {}
    for check, latest, cnt in result.all():
        if check.id in seen:
            continue
        seen[check.id] = _to_check_response(check, latest, cnt)
    items = list(seen.values())
    return DQCheckListResponse(items=items, total=len(items))


@router.post("", response_model=DQCheckResponse, status_code=201)
async def create_dq_check(body: DQCheckCreate, db: AsyncSession = Depends(get_db)):
    conn = await db.execute(select(Connection).where(Connection.id == body.connection_id))
    if not conn.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Connection not found")

    dup = await db.execute(select(DQCheck).where(DQCheck.name == body.name))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="DQ check name already exists")

    if body.team_id is not None and not await db.get(Team, body.team_id):
        raise HTTPException(status_code=400, detail="team_id not found")
    if body.alerting_profile_id is not None and not await db.get(
        AlertingProfile, body.alerting_profile_id
    ):
        raise HTTPException(status_code=400, detail="alerting_profile_id not found")

    check = DQCheck(
        name=body.name,
        description=body.description,
        connection_id=body.connection_id,
        team_id=body.team_id,
        alerting_profile_id=body.alerting_profile_id,
        data_source_name=body.data_source_name,
        sodacl_yaml=body.sodacl_yaml,
        tables=body.tables,
        check_categories=body.check_categories,
        tags=body.tags,
    )
    db.add(check)
    await db.flush()
    await db.refresh(check)
    result = await db.execute(
        select(DQCheck)
        .where(DQCheck.id == check.id)
        .options(selectinload(DQCheck.team), selectinload(DQCheck.alerting_profile))
    )
    check = result.scalar_one()
    return _to_check_response(check, None, 0)


@router.get("/summary", response_model=DQSummaryResponse)
async def dq_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(_list_stmt())
    seen: dict[uuid.UUID, DQCheckRun | None] = {}
    for check, latest, _cnt in result.all():
        if check.id not in seen:
            seen[check.id] = latest
    healthy = warning = failed = error = 0
    sum_passed = 0
    sum_total = 0
    for latest in seen.values():
        b = _bucket_latest(latest.status if latest else None)
        if b == "healthy":
            healthy += 1
        elif b == "warning":
            warning += 1
        elif b == "failed":
            failed += 1
        else:
            error += 1
        if latest and latest.checks_total > 0:
            sum_passed += latest.checks_passed
            sum_total += latest.checks_total

    total_checks = await db.scalar(select(func.count()).select_from(DQCheck))
    total_checks = int(total_checks or 0)
    overall = sum_passed / sum_total if sum_total > 0 else None

    return DQSummaryResponse(
        total_checks=total_checks,
        healthy=healthy,
        warning=warning,
        failed=failed,
        error=error,
        overall_pass_rate=overall,
    )


@router.get("/{check_id}", response_model=DQCheckDetailPayload)
async def get_dq_check(check_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DQCheck)
        .where(DQCheck.id == check_id)
        .options(selectinload(DQCheck.team), selectinload(DQCheck.alerting_profile))
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="DQ check not found")

    rc_result = await db.execute(
        select(func.count()).select_from(DQCheckRun).where(DQCheckRun.dq_check_id == check_id)
    )
    run_count = int(rc_result.scalar_one() or 0)

    latest_result = await db.execute(
        select(DQCheckRun)
        .where(DQCheckRun.dq_check_id == check_id)
        .order_by(DQCheckRun.run_at.desc(), DQCheckRun.id.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    runs_result = await db.execute(
        select(DQCheckRun)
        .where(DQCheckRun.dq_check_id == check_id)
        .order_by(DQCheckRun.run_at.desc(), DQCheckRun.id.desc())
        .limit(5)
    )
    recent = runs_result.scalars().all()

    return DQCheckDetailPayload(
        check=_to_check_response(check, latest, run_count),
        recent_runs=[DQRunResponse.model_validate(r) for r in recent],
    )


@router.put("/{check_id}", response_model=DQCheckResponse)
async def update_dq_check(
    check_id: uuid.UUID,
    body: DQCheckUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="DQ check not found")

    if body.team_id is not None and not await db.get(Team, body.team_id):
        raise HTTPException(status_code=400, detail="team_id not found")
    if body.alerting_profile_id is not None and not await db.get(
        AlertingProfile, body.alerting_profile_id
    ):
        raise HTTPException(status_code=400, detail="alerting_profile_id not found")

    if body.connection_id is not None:
        conn = await db.execute(select(Connection).where(Connection.id == body.connection_id))
        if not conn.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Connection not found")

    if body.name is not None and body.name != check.name:
        dup = await db.execute(select(DQCheck).where(DQCheck.name == body.name))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="DQ check name already exists")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(check, field, value)
    check.updated_at = datetime.now(timezone.utc)

    await db.flush()
    result = await db.execute(
        select(DQCheck)
        .where(DQCheck.id == check_id)
        .options(selectinload(DQCheck.team), selectinload(DQCheck.alerting_profile))
    )
    check = result.scalar_one()

    rc_result = await db.execute(
        select(func.count()).select_from(DQCheckRun).where(DQCheckRun.dq_check_id == check_id)
    )
    run_count = int(rc_result.scalar_one() or 0)
    latest_result = await db.execute(
        select(DQCheckRun)
        .where(DQCheckRun.dq_check_id == check_id)
        .order_by(DQCheckRun.run_at.desc(), DQCheckRun.id.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    return _to_check_response(check, latest, run_count)


@router.delete("/{check_id}", status_code=204)
async def delete_dq_check(check_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="DQ check not found")

    await db.execute(delete(DQCheckRun).where(DQCheckRun.dq_check_id == check_id))
    await db.execute(delete(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    await db.delete(check)


@router.post("/{check_id}/run", status_code=202)
async def trigger_dq_run(check_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="DQ check not found")
    async_result = run_dq_check.delay(str(check_id))
    return {"task_id": async_result.id, "status": "queued"}


@router.get("/{check_id}/runs", response_model=DQRunListResponse)
async def list_dq_runs(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    chk = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    if not chk.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="DQ check not found")

    count_result = await db.execute(
        select(func.count()).select_from(DQCheckRun).where(DQCheckRun.dq_check_id == check_id)
    )
    total = int(count_result.scalar_one() or 0)

    runs_result = await db.execute(
        select(DQCheckRun)
        .where(DQCheckRun.dq_check_id == check_id)
        .order_by(DQCheckRun.run_at.desc(), DQCheckRun.id.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = runs_result.scalars().all()
    return DQRunListResponse(
        items=[DQRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get("/{check_id}/runs/{run_id}", response_model=DQRunResponse)
async def get_dq_run(
    check_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DQCheckRun).where(
            DQCheckRun.id == run_id,
            DQCheckRun.dq_check_id == check_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return DQRunResponse.model_validate(run)
