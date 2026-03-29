from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.models.metric import DriftBaseline, DriftMetric
from sraosha.schemas.drift import (
    DriftAlertResponse,
    DriftBaselineResponse,
    DriftHistoryResponse,
    DriftMetricResponse,
)

router = APIRouter()


@router.get("/alerts", response_model=list[DriftAlertResponse])
async def drift_alerts(db: AsyncSession = Depends(get_db)):
    query = select(DriftMetric).where(
        (DriftMetric.is_warning == True) | (DriftMetric.is_breached == True)  # noqa: E712
    ).order_by(DriftMetric.measured_at.desc())
    result = await db.execute(query)
    metrics = result.scalars().all()

    baseline_query = select(DriftBaseline).where(DriftBaseline.is_trending_to_breach == True)  # noqa: E712
    baseline_result = await db.execute(baseline_query)
    baselines = {
        (b.contract_id, b.metric_type, b.table_name, b.column_name): b
        for b in baseline_result.scalars().all()
    }

    alerts = []
    for m in metrics:
        bl = baselines.get((m.contract_id, m.metric_type, m.table_name, m.column_name))
        alerts.append(
            DriftAlertResponse(
                contract_id=m.contract_id,
                metric_type=m.metric_type,
                table_name=m.table_name,
                column_name=m.column_name,
                current_value=m.value,
                warning_threshold=m.warning_threshold,
                breach_threshold=m.breach_threshold,
                trend_slope=bl.trend_slope if bl else None,
                estimated_breach_in_runs=bl.estimated_breach_in_runs if bl else None,
            )
        )
    return alerts


@router.get("/{contract_id}", response_model=list[DriftMetricResponse])
async def drift_status(contract_id: str, db: AsyncSession = Depends(get_db)):
    query = (
        select(DriftMetric)
        .where(DriftMetric.contract_id == contract_id)
        .order_by(DriftMetric.measured_at.desc())
    )
    result = await db.execute(query)
    metrics = result.scalars().all()

    seen: set[tuple] = set()
    latest: list[DriftMetricResponse] = []
    for m in metrics:
        key = (m.metric_type, m.table_name, m.column_name)
        if key not in seen:
            seen.add(key)
            latest.append(DriftMetricResponse.model_validate(m))
    return latest


@router.get("/{contract_id}/history", response_model=DriftHistoryResponse)
async def drift_history(
    contract_id: str,
    limit: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(DriftMetric)
        .where(DriftMetric.contract_id == contract_id)
        .order_by(DriftMetric.measured_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    metrics = result.scalars().all()
    return DriftHistoryResponse(
        items=[DriftMetricResponse.model_validate(m) for m in metrics]
    )


@router.get("/{contract_id}/baseline", response_model=list[DriftBaselineResponse])
async def drift_baseline(contract_id: str, db: AsyncSession = Depends(get_db)):
    query = select(DriftBaseline).where(DriftBaseline.contract_id == contract_id)
    result = await db.execute(query)
    baselines = result.scalars().all()
    return [DriftBaselineResponse.model_validate(b) for b in baselines]
