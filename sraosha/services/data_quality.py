"""DQ check queries and response mapping shared by API and dashboard."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import aliased, selectinload

from sraosha.models.dq_check import DQCheck
from sraosha.models.dq_run import DQCheckRun
from sraosha.schemas.data_quality import DQCheckResponse


def dq_checks_list_statement():
    """SQLAlchemy select for DQ checks with latest run and run count."""
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
            (latest_run.dq_check_id == DQCheck.id) & (latest_run.run_at == latest_sub.c.latest_at),
        )
        .outerjoin(run_count_sub, run_count_sub.c.cid == DQCheck.id)
        .options(selectinload(DQCheck.team), selectinload(DQCheck.alerting_profile))
        .order_by(DQCheck.name.asc())
    )


def dq_check_to_response(
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


def bucket_latest_dq_status(status: str | None) -> str:
    """Map raw DQ run status to summary bucket: healthy | warning | failed | error."""
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
