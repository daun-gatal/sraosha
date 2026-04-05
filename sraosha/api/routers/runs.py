from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.models.dq_check import DQCheck
from sraosha.models.dq_run import DQCheckRun
from sraosha.models.run import ValidationRun
from sraosha.schemas.data_quality import DQRunGlobalListResponse, DQRunListItem, DQRunResponse
from sraosha.schemas.run import (
    RunListResponse,
    RunSummaryItem,
    RunSummaryResponse,
    ValidationRunResponse,
)

router = APIRouter()


@router.get("", response_model=RunListResponse)
async def list_runs(
    contract_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(ValidationRun).order_by(ValidationRun.run_at.desc())
    count_query = select(func.count()).select_from(ValidationRun)

    if contract_id:
        query = query.where(ValidationRun.contract_id == contract_id)
        count_query = count_query.where(ValidationRun.contract_id == contract_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return RunListResponse(
        items=[ValidationRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get("/summary", response_model=RunSummaryResponse)
async def runs_summary(db: AsyncSession = Depends(get_db)):
    query = select(
        ValidationRun.contract_id,
        func.count().label("total_runs"),
        func.count().filter(ValidationRun.status == "passed").label("passed"),
        func.count().filter(ValidationRun.status == "failed").label("failed"),
        func.count().filter(ValidationRun.status == "error").label("error"),
    ).group_by(ValidationRun.contract_id)
    result = await db.execute(query)
    rows = result.all()

    items = [
        RunSummaryItem(
            contract_id=row.contract_id,
            total_runs=row.total_runs,
            passed=row.passed,
            failed=row.failed,
            error=row.error,
        )
        for row in rows
    ]
    return RunSummaryResponse(items=items)


@router.get("/dq", response_model=DQRunGlobalListResponse)
async def list_dq_runs_global(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count()).select_from(DQCheckRun))
    total = int(count_result.scalar() or 0)

    result = await db.execute(
        select(DQCheckRun, DQCheck.name)
        .join(DQCheck, DQCheck.id == DQCheckRun.dq_check_id)
        .order_by(DQCheckRun.run_at.desc(), DQCheckRun.id.desc())
        .offset(offset)
        .limit(limit)
    )
    items = [
        DQRunListItem(
            **DQRunResponse.model_validate(run).model_dump(),
            dq_check_name=name,
        )
        for run, name in result.all()
    ]
    return DQRunGlobalListResponse(items=items, total=total)


@router.get("/{run_id}", response_model=ValidationRunResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    import uuid as uuid_mod

    try:
        uid = uuid_mod.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    result = await db.execute(select(ValidationRun).where(ValidationRun.id == uid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return ValidationRunResponse.model_validate(run)
