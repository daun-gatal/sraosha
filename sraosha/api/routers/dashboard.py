"""Server-rendered dashboard views using Jinja2 templates."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import yaml
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.datastructures import UploadFile

from sraosha.api.contract_yaml import (
    connection_id_to_name_map_from_connections,
    dict_to_yaml_string,
    form_to_yaml_dict,
    yaml_dict_to_form,
    yaml_string_to_dict,
)
from sraosha.api.deps import get_db
from sraosha.api.routers.data_quality import _bucket_latest, _list_stmt
from sraosha.api.routers.schedules import _compute_next_run
from sraosha.compliance.scoring import rolling_30d_window, sparkline_svg_points
from sraosha.dq.check_templates import TEMPLATES as DQ_CHECK_TEMPLATES
from sraosha.dq.config_builder import (
    SODA_CONNECTOR_TYPES,
    explicit_data_source_for_form,
    resolve_data_source_name,
)
from sraosha.impact.analyzer import ImpactAnalyzer
from sraosha.models.alerting import AlertingProfile, AlertingProfileChannel
from sraosha.models.connection import Connection
from sraosha.models.contract import Contract
from sraosha.models.dq_check import DQCheck
from sraosha.models.dq_run import DQCheckRun
from sraosha.models.dq_schedule import DQSchedule
from sraosha.models.run import ValidationRun
from sraosha.models.schedule import ValidationSchedule
from sraosha.models.team import ComplianceScore, Team
from sraosha.schemas.dq_wizard import parse_dq_generate_params
from sraosha.tasks.dq_scan import run_dq_check

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _form_text(val: str | UploadFile | None, default: str = "") -> str:
    """Coerce Starlette form values to ``str`` (HTML forms use strings; uploads are ignored)."""
    if val is None:
        return default
    if isinstance(val, UploadFile):
        return default
    return val


router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get("/search", response_class=HTMLResponse)
async def global_search(
    request: Request,
    q: str = Query("", alias="q"),
    db: AsyncSession = Depends(get_db),
):
    q = (q or "").strip()
    contracts = []
    teams = []
    if len(q) >= 1:
        cr = await db.execute(
            select(Contract)
            .where(
                Contract.title.ilike(f"%{q}%") | Contract.contract_id.ilike(f"%{q}%"),
            )
            .order_by(Contract.title)
            .limit(12)
        )
        contracts = [
            {"contract_id": c.contract_id, "title": c.title or c.contract_id}
            for c in cr.scalars().all()
        ]
        tr = await db.execute(
            select(Team.name).where(Team.name.ilike(f"%{q}%")).order_by(Team.name).limit(8)
        )
        teams = [r[0] for r in tr.all()]
    return templates.TemplateResponse(
        request,
        "partials/search_results.html",
        {"q": q, "contracts": contracts, "teams": teams},
    )


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request, db: AsyncSession = Depends(get_db)):
    contracts_result = await db.execute(
        select(Contract).options(selectinload(Contract.team)).order_by(Contract.created_at.desc())
    )
    contracts = contracts_result.scalars().all()

    summary_query = select(
        ValidationRun.contract_id,
        func.count().label("total_runs"),
        func.count().filter(ValidationRun.status == "passed").label("passed"),
        func.count().filter(ValidationRun.status == "failed").label("failed"),
        func.count().filter(ValidationRun.status == "error").label("error"),
        func.max(ValidationRun.run_at).label("last_run_at"),
    ).group_by(ValidationRun.contract_id)
    summary_result = await db.execute(summary_query)
    summary_map = {row.contract_id: row for row in summary_result.all()}

    rows = []
    total_failed = 0
    passing_count = 0
    now = datetime.now(timezone.utc)
    for c in contracts:
        s = summary_map.get(c.contract_id)
        total_runs = s.total_runs if s else 0
        failed = s.failed if s else 0
        total_failed += failed
        passed_n = s.passed if s else 0
        pass_rate = int(round(passed_n / total_runs * 100)) if total_runs else None
        last_run_at = s.last_run_at if s else None
        last_run_rel = _relative_time(last_run_at) if last_run_at else None

        if s and s.total_runs > 0:
            if failed > 0:
                status = "failing"
            else:
                status = "passing"
                passing_count += 1
        else:
            status = "unknown"

        rows.append(
            {
                "contract_id": c.contract_id,
                "title": c.title,
                "owner_team": c.owner_team,
                "enforcement_mode": c.enforcement_mode,
                "status": status,
                "total_runs": total_runs,
                "pass_rate": pass_rate,
                "last_run_rel": last_run_rel,
            }
        )

    total = len(contracts)
    pass_pct_num = int(passing_count / total * 100) if total else 0
    pct_display = f"{pass_pct_num}%" if total else "—"

    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = start_today + timedelta(days=1)
    sched_today = await db.execute(
        select(func.count())
        .select_from(ValidationSchedule)
        .where(
            ValidationSchedule.is_enabled == True,  # noqa: E712
            ValidationSchedule.next_run_at >= start_today,
            ValidationSchedule.next_run_at < end_today,
        )
    )
    scheduled_today = sched_today.scalar() or 0

    activity_result = await db.execute(
        select(ValidationRun).order_by(ValidationRun.run_at.desc()).limit(12)
    )
    activity_runs = activity_result.scalars().all()
    activity = []
    titles = {c.contract_id: c.title for c in contracts}
    for r in activity_runs:
        activity.append(
            {
                "run_id": str(r.id),
                "contract_id": r.contract_id,
                "title": titles.get(r.contract_id, r.contract_id),
                "status": r.status,
                "run_at": r.run_at,
                "when": _relative_time(r.run_at),
                "checks": f"{r.checks_passed}/{r.checks_total}",
            }
        )

    dq_total = await db.scalar(select(func.count()).select_from(DQCheck)) or 0
    dq_healthy = 0
    if dq_total:
        latest_sub = (
            select(
                DQCheckRun.dq_check_id,
                func.max(DQCheckRun.run_at).label("latest_at"),
            )
            .group_by(DQCheckRun.dq_check_id)
            .subquery()
        )
        latest_runs = await db.execute(
            select(DQCheckRun.status).join(
                latest_sub,
                (DQCheckRun.dq_check_id == latest_sub.c.dq_check_id)
                & (DQCheckRun.run_at == latest_sub.c.latest_at),
            )
        )
        for (st,) in latest_runs.all():
            if st and st.lower() in ("passed", "pass"):
                dq_healthy += 1

    dq_display = f"{dq_healthy}/{dq_total}" if dq_total else "—"

    dq_checks_result = await db.execute(select(DQCheck).order_by(DQCheck.name).limit(8))
    all_dq_checks = list(dq_checks_result.scalars().all())

    dq_latest_runs: dict[uuid_mod.UUID, DQCheckRun] = {}
    if all_dq_checks:
        lr_sub = (
            select(
                DQCheckRun.dq_check_id,
                func.max(DQCheckRun.run_at).label("latest_at"),
            )
            .group_by(DQCheckRun.dq_check_id)
            .subquery()
        )
        lr_result = await db.execute(
            select(DQCheckRun).join(
                lr_sub,
                (DQCheckRun.dq_check_id == lr_sub.c.dq_check_id)
                & (DQCheckRun.run_at == lr_sub.c.latest_at),
            )
        )
        for run in lr_result.scalars().all():
            dq_latest_runs[run.dq_check_id] = run

    dq_rows = []
    for chk in all_dq_checks:
        lr = dq_latest_runs.get(chk.id)
        dq_rows.append(
            {
                "id": str(chk.id),
                "name": chk.name,
                "status": lr.status.lower() if lr else "no_runs",
                "run_at_rel": _relative_time(lr.run_at) if lr else None,
                "checks_passed": lr.checks_passed if lr else 0,
                "checks_total": lr.checks_total if lr else 0,
                "checks_failed": lr.checks_failed if lr else 0,
            }
        )

    stats = [
        {
            "id": "total",
            "label": "Total Contracts",
            "value": total,
            "hint": "Registered",
        },
        {
            "id": "pass_rate",
            "label": "Pass rate",
            "value": pct_display,
            "hint": "Contracts with all runs passing",
        },
        {
            "id": "dq_health",
            "label": "DQ Checks",
            "value": dq_display,
            "hint": "Healthy / total DQ checks",
        },
        {
            "id": "failed_runs",
            "label": "Failed runs",
            "value": total_failed,
            "hint": "Sum of failed validations",
        },
        {
            "id": "schedules",
            "label": "Schedules today",
            "value": scheduled_today,
            "hint": "Runs due today (UTC)",
        },
    ]

    return templates.TemplateResponse(
        request,
        "overview.html",
        {
            "active_page": "Overview",
            "stats": stats,
            "pass_pct_num": pass_pct_num,
            "contracts": sorted(rows, key=lambda x: x["title"] or "")[:8],
            "total_contracts": total,
            "activity": activity,
            "dq_checks": dq_rows,
            "dq_total": dq_total,
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_uuid(val: object) -> uuid_mod.UUID | None:
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return uuid_mod.UUID(s)
    except ValueError:
        return None


async def _resolve_team_id_from_doc(
    db: AsyncSession, xs: dict, info: dict
) -> tuple[uuid_mod.UUID | None, list[str]]:
    """Resolve team FK from x-sraosha.

    Explicit team_id UUID must exist; owner_team/info.owner only match existing teams.
    """
    errs: list[str] = []
    raw_tid = xs.get("team_id")
    if raw_tid is not None and str(raw_tid).strip():
        tid = _parse_uuid(raw_tid)
        if tid is None:
            return None, ["x-sraosha.team_id must be a valid UUID if set."]
        t = await db.get(Team, tid)
        if not t:
            return None, ["x-sraosha.team_id does not match any registered team."]
        return t.id, errs
    name = xs.get("owner_team") or info.get("owner")
    if isinstance(name, str) and name.strip():
        r = await db.execute(select(Team.id).where(Team.name == name.strip()))
        return r.scalar_one_or_none(), errs
    return None, errs


async def _resolve_alerting_profile_id_from_doc(db: AsyncSession, xs: dict) -> uuid_mod.UUID | None:
    aid = _parse_uuid(xs.get("alerting_profile_id"))
    if aid is None:
        return None
    ap = await db.get(AlertingProfile, aid)
    return ap.id if ap else None


async def _enrich_doc_x_sraosha(
    db: AsyncSession,
    doc: dict,
    team_id: uuid_mod.UUID | None,
    alerting_profile_id: uuid_mod.UUID | None,
) -> None:
    xs = doc.setdefault("x-sraosha", {})
    if not isinstance(xs, dict):
        xs = {}
        doc["x-sraosha"] = xs
    if team_id:
        xs["team_id"] = str(team_id)
        t = await db.get(Team, team_id)
        if t:
            xs["owner_team"] = t.name
    elif "team_id" in xs:
        del xs["team_id"]
    if alerting_profile_id:
        xs["alerting_profile_id"] = str(alerting_profile_id)
    elif "alerting_profile_id" in xs:
        del xs["alerting_profile_id"]


async def _teams_and_alerting_profiles(
    db: AsyncSession,
) -> tuple[list[Team], list[AlertingProfile]]:
    tr = await db.execute(select(Team).order_by(Team.name))
    pr = await db.execute(select(AlertingProfile).order_by(AlertingProfile.name))
    return list(tr.scalars().all()), list(pr.scalars().all())


def _relative_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


# ---------------------------------------------------------------------------
# Compliance leaderboard
# ---------------------------------------------------------------------------


async def _compliance_page_context(db: AsyncSession) -> dict:
    """Build template context for the compliance dashboard (teams, KPIs, at-risk, failures)."""
    now = datetime.now(timezone.utc)
    cutoff, _, _, _ = rolling_30d_window(now)

    teams_result = await db.execute(select(Team).order_by(Team.name))
    teams = list(teams_result.scalars().all())

    contracts_result = await db.execute(select(Contract).options(selectinload(Contract.team)))
    all_contracts = list(contracts_result.scalars().all())
    contracts_by_team: dict[str, list[Contract]] = {}
    for c in all_contracts:
        if not c.team_id or not c.team:
            continue
        contracts_by_team.setdefault(c.team.name, []).append(c)
    for lst in contracts_by_team.values():
        lst.sort(key=lambda x: (x.title or x.contract_id).lower())

    summary_query = (
        select(
            ValidationRun.contract_id,
            func.count().label("total_runs"),
            func.count().filter(ValidationRun.status == "passed").label("passed"),
            func.count().filter(ValidationRun.status == "failed").label("failed"),
            func.count().filter(ValidationRun.status == "error").label("error"),
        )
        .where(ValidationRun.run_at >= cutoff)
        .group_by(ValidationRun.contract_id)
    )
    summary_result = await db.execute(summary_query)
    run_summary = {row.contract_id: row for row in summary_result.all()}

    title_map = {c.contract_id: c.title or c.contract_id for c in all_contracts}

    max_computed = await db.scalar(select(func.max(ComplianceScore.computed_at)))

    has_any_runs = bool(
        await db.scalar(
            select(func.count()).select_from(ValidationRun).where(ValidationRun.run_at >= cutoff)
        )
    )

    contracts_linked_to_team = (
        await db.scalar(
            select(func.count()).select_from(Contract).where(Contract.team_id.isnot(None))
        )
        or 0
    )
    contracts_unlinked = (
        await db.scalar(
            select(func.count()).select_from(Contract).where(Contract.team_id.is_(None))
        )
        or 0
    )

    entries_raw: list[dict] = []
    for team in teams:
        tc = contracts_by_team.get(team.name, [])
        contracts_owned = len(tc)

        total_runs = 0
        passed = 0
        failed = 0
        err = 0
        for c in tc:
            s = run_summary.get(c.contract_id)
            if not s:
                continue
            total_runs += s.total_runs
            passed += s.passed or 0
            failed += s.failed or 0
            err += s.error or 0

        live_pass_pct: float | None = None
        if total_runs > 0:
            live_pass_pct = round(100.0 * passed / total_runs, 1)

        violations_live = failed + err

        hist_result = await db.execute(
            select(ComplianceScore)
            .where(ComplianceScore.team_id == team.id)
            .order_by(ComplianceScore.period_end.desc())
            .limit(8)
        )
        hist = list(hist_result.scalars().all())
        latest = hist[0] if hist else None

        stored_score = round(latest.score, 1) if latest else None
        spark = [round(h.score, 1) for h in reversed(hist)]
        spark_pts = sparkline_svg_points(spark)

        contract_rows = []
        for c in tc:
            s = run_summary.get(c.contract_id)
            tr = s.total_runs if s else 0
            pr = None
            if s and tr:
                pr = int(round((s.passed or 0) / tr * 100))
            contract_rows.append(
                {
                    "contract_id": c.contract_id,
                    "title": c.title or c.contract_id,
                    "pass_rate": pr,
                    "total_runs": tr,
                }
            )

        if latest is not None:
            display_score = round(latest.score, 1)
            score_source = "snapshot"
            rank_sort = float(latest.score)
        elif live_pass_pct is not None:
            display_score = live_pass_pct
            score_source = "live"
            rank_sort = float(live_pass_pct)
        else:
            display_score = None
            score_source = "none"
            rank_sort = -1.0

        entries_raw.append(
            {
                "team_id": str(team.id),
                "team_name": team.name,
                "rank_sort": rank_sort,
                "display_score": display_score,
                "score": display_score,
                "score_source": score_source,
                "stored_score": stored_score,
                "live_pass_pct": live_pass_pct,
                "contracts_owned": contracts_owned,
                "violations_30d": violations_live,
                "total_runs_30d": total_runs,
                "score_sparkline": spark,
                "sparkline_points": spark_pts,
                "contracts_detail": contract_rows,
                "has_snapshot": latest is not None,
            }
        )

    entries_raw.sort(key=lambda x: x["rank_sort"], reverse=True)
    items: list[dict] = []
    for i, e in enumerate(entries_raw, 1):
        row = {k: v for k, v in e.items() if k != "rank_sort"}
        row["rank"] = i
        items.append(row)

    at_risk: list[dict] = []
    for c in all_contracts:
        if not c.team_id:
            continue
        s = run_summary.get(c.contract_id)
        if not s or s.total_runs == 0:
            continue
        pr = int(round((s.passed or 0) / s.total_runs * 100))
        at_risk.append(
            {
                "contract_id": c.contract_id,
                "title": c.title or c.contract_id,
                "owner_team": c.owner_team,
                "pass_rate": pr,
                "total_runs": s.total_runs,
            }
        )
    at_risk.sort(key=lambda x: x["pass_rate"])
    at_risk = at_risk[:8]

    fail_result = await db.execute(
        select(ValidationRun)
        .where(
            ValidationRun.status.in_(["failed", "error"]),
            ValidationRun.run_at >= cutoff,
        )
        .order_by(ValidationRun.run_at.desc())
        .limit(10)
    )
    recent_failures: list[dict] = []
    for r in fail_result.scalars().all():
        matched = next((x for x in all_contracts if x.contract_id == r.contract_id), None)
        recent_failures.append(
            {
                "contract_id": r.contract_id,
                "title": title_map.get(r.contract_id, r.contract_id),
                "team": matched.owner_team if matched else None,
                "status": r.status,
                "when": _relative_time(r.run_at),
            }
        )

    scores_for_avg = [e["display_score"] for e in items if e["display_score"] is not None]
    org_avg = round(sum(scores_for_avg) / len(scores_for_avg), 1) if scores_for_avg else None

    teams_needing_attention = 0
    for e in items:
        if e["display_score"] is None and e["contracts_owned"] > 0:
            teams_needing_attention += 1
        elif e["display_score"] is not None and e["display_score"] < 70:
            teams_needing_attention += 1

    total_violations = sum(e["violations_30d"] for e in items)

    def _utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    snapshot_stale = max_computed is None or (now - _utc(max_computed)) > timedelta(days=7)

    last_computed_display = None
    if max_computed:
        last_computed_display = _relative_time(_utc(max_computed))

    show_estimated_banner = max_computed is None
    snapshot_banner_soft = show_estimated_banner and len(items) > 0

    return {
        "entries": items,
        "entries_json": json.dumps(items),
        "kpis": {
            "org_avg": org_avg,
            "teams_tracked": len(teams),
            "teams_needing_attention": teams_needing_attention,
            "total_violations_30d": total_violations,
            "last_computed_rel": last_computed_display,
            "has_snapshot_computed": max_computed is not None,
        },
        "at_risk": at_risk,
        "recent_failures": recent_failures,
        "has_teams": len(teams) > 0,
        "contracts_linked_to_team": int(contracts_linked_to_team),
        "contracts_unlinked": int(contracts_unlinked),
        "has_any_runs": has_any_runs,
        "show_estimated_banner": show_estimated_banner,
        "snapshot_banner_soft": snapshot_banner_soft,
        "snapshot_stale": snapshot_stale,
    }


@router.get("/compliance", response_class=HTMLResponse)
async def compliance_page(request: Request, db: AsyncSession = Depends(get_db)):
    ctx = await _compliance_page_context(db)
    ctx["active_page"] = "Compliance"
    return templates.TemplateResponse(request, "compliance.html", ctx)


# ---------------------------------------------------------------------------
# Impact map
# ---------------------------------------------------------------------------


async def _build_analyzer(db: AsyncSession) -> ImpactAnalyzer:
    result = await db.execute(
        select(Contract).where(Contract.is_active == True)  # noqa: E712
    )
    contracts = result.scalars().all()
    contract_dicts = []
    for c in contracts:
        try:
            parsed = yaml.safe_load(c.raw_yaml)
            if parsed:
                contract_dicts.append(parsed)
        except yaml.YAMLError:
            pass
    return ImpactAnalyzer(contract_dicts)


async def _contract_run_status_map(db: AsyncSession) -> dict[str, str]:
    """Latest validation status per contract_id."""
    runs_result = await db.execute(select(ValidationRun).order_by(ValidationRun.run_at.desc()))
    status_map: dict[str, str] = {}
    for r in runs_result.scalars().all():
        if r.contract_id not in status_map:
            status_map[r.contract_id] = r.status
    return status_map


async def _dq_latest_run_status_map(db: AsyncSession) -> dict[uuid_mod.UUID, str]:
    """Latest DQ run status per check id."""
    runs_result = await db.execute(select(DQCheckRun).order_by(DQCheckRun.run_at.desc()))
    status_map: dict[uuid_mod.UUID, str] = {}
    for r in runs_result.scalars().all():
        if r.dq_check_id not in status_map:
            status_map[r.dq_check_id] = r.status
    return status_map


def _dq_templates_for_js() -> list[dict]:
    """Serialise check template metadata for the JS wizard (no callables)."""
    out = []
    for key, meta in DQ_CHECK_TEMPLATES.items():
        out.append(
            {
                "key": key,
                "label": meta["label"],
                "description": meta.get("description", ""),
                "icon": meta.get("icon", ""),
                "category": meta.get("category", "integrity"),
                "soda_section": meta.get("soda_section"),
                "needs_column": meta.get("needs_column", False),
                "column_types": meta.get("column_types", []),
                "params": meta.get("params", []),
            }
        )
    return out


@router.get("/impact", response_class=HTMLResponse)
async def impact_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    focus: str | None = Query(None, description="Center lineage on this contract id"),
    upstream_depth: int = Query(2, ge=0, le=10),
    downstream_depth: int = Query(2, ge=0, le=10),
):
    analyzer = await _build_analyzer(db)
    if focus:
        graph_data = analyzer.lineage_json(focus, upstream_depth, downstream_depth)
    else:
        graph_data = analyzer.to_json()
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    status_map = await _contract_run_status_map(db)

    contract_rows = await db.execute(
        select(Contract.contract_id, Contract.title, Team.name)
        .outerjoin(Team, Contract.team_id == Team.id)
        .where(Contract.is_active == True)  # noqa: E712
    )
    all_contracts = []
    titles: dict[str, str] = {}
    owners: dict[str, str] = {}
    for r in contract_rows.all():
        titles[r[0]] = r[1]
        owners[r[0]] = r[2] or ""
        all_contracts.append({"id": r[0], "title": r[1], "owner": r[2] or ""})

    # Build fields_by_contract from graph data
    fields_by_contract: dict[str, dict[str, list[str]]] = {}
    for cf in analyzer.graph._contract_fields.values():
        fields_by_contract[cf.contract_id] = {
            table: list(field_names) for table, field_names in cf.tables.items()
        }

    cy_nodes = []
    for n in nodes:
        cid = n["id"]
        st = status_map.get(cid, "none")
        title = titles.get(cid, n.get("label", cid))
        cy_nodes.append(
            {
                "data": {
                    "id": cid,
                    "title": title,
                    "subtitle": cid,
                    "label": f"{title}\n{cid}",
                    "platform": n.get("platform") or "",
                    "platforms": n.get("platforms") or [],
                    "is_focus": "1" if focus and cid == focus else "0",
                    "status": st,
                    "owner_team": owners.get(cid, n.get("owner_team", "")),
                    "tables": n.get("tables", []),
                    "upstream_count": n.get("upstream_count", 0),
                    "downstream_count": n.get("downstream_count", 0),
                },
            }
        )
    cy_edges = []
    for i, e in enumerate(edges):
        sf = e.get("shared_fields") or []
        fm = e.get("field_mapping") or {}
        if e.get("edge_type") == "explicit" and fm:
            elabel = f"{len(fm)} col. mapping"
        elif sf:
            elabel = f"{len(sf)} fields"
        else:
            elabel = e.get("edge_type", "link")
        cy_edges.append(
            {
                "data": {
                    "id": f"e{i}",
                    "source": e["source"],
                    "target": e["target"],
                    "label": elabel,
                    "edge_type": e.get("edge_type", "inferred"),
                    "shared_fields": sf,
                    "field_mapping": fm,
                    "column_pairs": e.get("column_pairs") or [],
                },
            }
        )
    graph_elements = {"nodes": cy_nodes, "edges": cy_edges}

    full_graph = analyzer.to_json()
    total_nodes = len(full_graph["nodes"])
    total_edges = len(full_graph["edges"])
    isolated = sum(1 for n in full_graph["nodes"] if n.get("degree", 0) == 0)
    avg_connections = round(total_edges / total_nodes, 1) if total_nodes else 0
    explicit_count = sum(1 for e in full_graph["edges"] if e.get("edge_type") == "explicit")
    inferred_count = total_edges - explicit_count

    stats = {
        "total_contracts": total_nodes,
        "total_dependencies": total_edges,
        "avg_connections": avg_connections,
        "isolated": isolated,
        "explicit_links": explicit_count,
        "inferred_links": inferred_count,
    }

    return templates.TemplateResponse(
        request,
        "impact.html",
        {
            "active_page": "Impact Map",
            "graph_elements_json": json.dumps(graph_elements),
            "fields_by_contract_json": json.dumps(fields_by_contract),
            "nodes": nodes,
            "all_contracts": all_contracts,
            "stats": stats,
            "lineage_focus": focus or "",
            "lineage_upstream_depth": upstream_depth,
            "lineage_downstream_depth": downstream_depth,
        },
    )


@router.post("/impact/analyze", response_class=HTMLResponse)
async def impact_analyze(
    request: Request,
    contract_id: str = Form(""),
    changed_fields: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    if not contract_id or not changed_fields.strip():
        return templates.TemplateResponse(
            request,
            "partials/impact_result.html",
            {"error": "Please select a contract and enter at least one field."},
        )

    contract_result = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
    if not contract_result.scalar_one_or_none():
        return templates.TemplateResponse(
            request,
            "partials/impact_result.html",
            {"error": f"Contract '{contract_id}' not found."},
        )

    analyzer = await _build_analyzer(db)
    fields = [f.strip() for f in changed_fields.split(",") if f.strip()]
    impact = analyzer.analyze(contract_id, fields)
    affected_ids = list(impact["directly_affected"]) + list(impact["transitively_affected"])

    status_map = await _contract_run_status_map(db)
    title_rows = await db.execute(
        select(Contract.contract_id, Contract.title, Team.name)
        .outerjoin(Team, Contract.team_id == Team.id)
        .where(Contract.is_active == True)  # noqa: E712
    )
    contract_info = {r[0]: {"title": r[1], "owner": r[2] or ""} for r in title_rows.all()}

    directly_affected_contracts = []
    for cid in impact["directly_affected"]:
        info = contract_info.get(cid, {})
        directly_affected_contracts.append(
            {
                "id": cid,
                "title": info.get("title", cid),
                "owner": info.get("owner", ""),
                "status": status_map.get(cid, "none"),
            }
        )
    transitively_affected_contracts = []
    for cid in impact["transitively_affected"]:
        info = contract_info.get(cid, {})
        transitively_affected_contracts.append(
            {
                "id": cid,
                "title": info.get("title", cid),
                "owner": info.get("owner", ""),
                "status": status_map.get(cid, "none"),
            }
        )

    return templates.TemplateResponse(
        request,
        "partials/impact_result.html",
        {
            "severity": impact["severity"],
            "directly_affected": directly_affected_contracts,
            "transitively_affected": transitively_affected_contracts,
            "affected_ids_json": json.dumps(affected_ids),
            "changed_fields": fields,
        },
    )


@router.post("/impact/link", response_class=HTMLResponse)
async def impact_link(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Patch the downstream contract's YAML to add/merge column-mapped dependency."""
    form = await request.form()
    upstream_id = form.get("upstream_id", "")
    downstream_id = form.get("downstream_id", "")

    if not upstream_id or not downstream_id or upstream_id == downstream_id:
        return RedirectResponse("/ui/impact", status_code=303)

    field_upstreams = form.getlist("field_upstream[]")
    field_locals = form.getlist("field_local[]")

    field_mapping: dict[str, str] = {}
    for up, lo in zip(field_upstreams, field_locals):
        up_s, lo_s = _form_text(up), _form_text(lo)
        if up_s and lo_s:
            field_mapping[up_s] = lo_s

    result = await db.execute(select(Contract).where(Contract.contract_id == downstream_id))
    contract = result.scalar_one_or_none()
    if not contract:
        return RedirectResponse("/ui/impact", status_code=303)

    try:
        parsed = yaml.safe_load(contract.raw_yaml) or {}
    except yaml.YAMLError:
        parsed = {}

    x_sraosha = parsed.setdefault("x-sraosha", {})
    depends_on = x_sraosha.get("depends_on", [])
    if not isinstance(depends_on, list):
        depends_on = []

    existing_entry = None
    for entry in depends_on:
        if isinstance(entry, dict) and entry.get("contract") == upstream_id:
            existing_entry = entry
            break

    if existing_entry is not None:
        existing_fields = existing_entry.get("fields", {})
        if not isinstance(existing_fields, dict):
            existing_fields = {}
        existing_fields.update(field_mapping)
        existing_entry["fields"] = existing_fields
    else:
        new_entry: dict = {"contract": upstream_id}
        if field_mapping:
            new_entry["fields"] = field_mapping
        depends_on.append(new_entry)

    x_sraosha["depends_on"] = depends_on
    parsed["x-sraosha"] = x_sraosha

    contract.raw_yaml = yaml.dump(parsed, default_flow_style=False, sort_keys=False)
    contract.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return RedirectResponse("/ui/impact", status_code=303)


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------


def _empty_form_data() -> dict:
    """Return default values for an empty contract form."""
    return {
        "contract_id": "",
        "spec_version": "1.1.0",
        "title": "",
        "version": "1.0.0",
        "description": "",
        "owner": "",
        "contact_name": "",
        "contact_email": "",
        "servers": [],
        "models": [],
        "owner_team": "",
        "team_id": "",
        "alerting_profile_id": "",
        "enforcement_mode": "block",
        "depends_on": [],
        "notify_slack": "",
        "notify_email": "",
    }


async def _team_names_for_filter(db: AsyncSession) -> list[str]:
    """Team names for contract list filter."""
    result = await db.execute(select(Team.name).order_by(Team.name))
    return [r[0] for r in result.all()]


@router.get("/contracts", response_class=HTMLResponse)
async def contracts_list(
    request: Request,
    q: str = Query("", alias="q"),
    team: str = Query("", alias="team"),
    sort: str = Query("newest"),
    db: AsyncSession = Depends(get_db),
):
    """Searchable / filterable contract list."""
    query = select(Contract).options(selectinload(Contract.team))
    if q:
        query = query.where(Contract.title.ilike(f"%{q}%") | Contract.contract_id.ilike(f"%{q}%"))
    if team:
        query = query.join(Team, Contract.team_id == Team.id).where(Team.name == team)

    contracts_result = await db.execute(query)
    contracts = list(contracts_result.scalars().all())

    summary_query = select(
        ValidationRun.contract_id,
        func.count().label("total_runs"),
        func.count().filter(ValidationRun.status == "passed").label("passed"),
        func.count().filter(ValidationRun.status == "failed").label("failed"),
        func.max(ValidationRun.run_at).label("last_run_at"),
    ).group_by(ValidationRun.contract_id)
    summary_result = await db.execute(summary_query)
    summary_map = {row.contract_id: row for row in summary_result.all()}

    rows: list[dict[str, Any]] = []
    for c in contracts:
        s = summary_map.get(c.contract_id)
        total_runs = s.total_runs if s else 0
        failed = s.failed if s else 0
        passed_n = s.passed if s else 0
        if s and s.total_runs > 0:
            status = "failing" if failed > 0 else "passing"
        else:
            status = "unknown"
        pass_rate = int(round(passed_n / total_runs * 100)) if total_runs else None
        last_at = s.last_run_at if s else None
        rows.append(
            {
                "contract_id": c.contract_id,
                "title": c.title,
                "description": c.description,
                "owner_team": c.owner_team,
                "enforcement_mode": c.enforcement_mode,
                "is_active": c.is_active,
                "status": status,
                "total_runs": total_runs,
                "created_at": c.created_at,
                "pass_rate": pass_rate,
                "last_run_at": last_at,
                "last_run_rel": _relative_time(last_at) if last_at else None,
            }
        )

    if sort == "name":
        rows.sort(key=lambda x: str(x.get("title") or "").lower())
    elif sort == "runs":
        rows.sort(key=lambda x: -int(x.get("total_runs") or 0))
    elif sort == "health":

        def _health_key(x: dict[str, Any]) -> tuple[int, float]:
            order = {"failing": 0, "unknown": 1, "passing": 2}
            st = str(x.get("status") or "")
            pr = x.get("pass_rate")
            pr_f = float(pr) if pr is not None else 0.0
            return (order.get(st, 9), -pr_f)

        rows.sort(key=_health_key)
    else:
        rows.sort(
            key=lambda x: cast(datetime, x["created_at"]),
            reverse=True,
        )

    teams = await _team_names_for_filter(db)

    return templates.TemplateResponse(
        request,
        "contracts_list.html",
        {
            "active_page": "Contracts",
            "contracts": rows,
            "teams": teams,
            "q": q,
            "selected_team": team,
            "sort": sort,
        },
    )


async def _get_connections(db: AsyncSession) -> list:
    result = await db.execute(select(Connection).order_by(Connection.name))
    return list(result.scalars().all())


async def _all_contract_ids(db: AsyncSession) -> list[dict]:
    """Lightweight list of active contracts for dependency selectors."""
    rows = await db.execute(
        select(Contract.contract_id, Contract.title)
        .where(Contract.is_active == True)  # noqa: E712
        .order_by(Contract.title)
    )
    return [{"id": r[0], "title": r[1]} for r in rows.all()]


async def _fields_by_contract_map(db: AsyncSession) -> dict[str, dict[str, list[str]]]:
    """Build {contract_id: {table: [fields]}} from all active contracts' YAML."""
    result = await db.execute(
        select(Contract.contract_id, Contract.raw_yaml).where(Contract.is_active == True)  # noqa: E712
    )
    fbc: dict[str, dict[str, list[str]]] = {}
    for cid, raw in result.all():
        try:
            doc = yaml.safe_load(raw) if raw else {}
        except yaml.YAMLError:
            doc = {}
        models = doc.get("models", {}) if isinstance(doc, dict) else {}
        tables: dict[str, list[str]] = {}
        for mname, mdef in models.items():
            if isinstance(mdef, dict):
                fields = mdef.get("fields", {})
                tables[mname] = list(fields.keys()) if isinstance(fields, dict) else []
        fbc[cid] = tables
    return fbc


@router.get("/contracts/new", response_class=HTMLResponse)
async def contract_new(request: Request, db: AsyncSession = Depends(get_db)):
    """Show empty create-contract form."""
    form_data = _empty_form_data()
    raw_yaml = dict_to_yaml_string(form_to_yaml_dict(form_data))
    connections = await _get_connections(db)
    dep_contracts = await _all_contract_ids(db)
    fbc = await _fields_by_contract_map(db)
    teams, alerting_profiles = await _teams_and_alerting_profiles(db)
    return templates.TemplateResponse(
        request,
        "contract_form.html",
        {
            "active_page": "Contracts",
            "mode": "create",
            "form": form_data,
            "raw_yaml": raw_yaml,
            "errors": [],
            "connections": connections,
            "dep_contracts": dep_contracts,
            "fields_by_contract_json": json.dumps(fbc),
            "teams": teams,
            "alerting_profiles": alerting_profiles,
        },
    )


@router.post("/contracts/new", response_class=HTMLResponse)
async def contract_create(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle contract creation from the form."""
    form_dict = _multi_items_to_dict(await request.form())

    raw_yaml_input = form_dict.get("raw_yaml", "").strip()
    errors: list[str] = []

    if raw_yaml_input:
        try:
            doc = yaml_string_to_dict(raw_yaml_input)
        except ValueError as exc:
            errors.append(str(exc))
            connections = await _get_connections(db)
            dep_contracts = await _all_contract_ids(db)
            fbc = await _fields_by_contract_map(db)
            teams, alerting_profiles = await _teams_and_alerting_profiles(db)
            return templates.TemplateResponse(
                request,
                "contract_form.html",
                {
                    "active_page": "Contracts",
                    "mode": "create",
                    "form": _empty_form_data(),
                    "raw_yaml": raw_yaml_input,
                    "errors": errors,
                    "connections": connections,
                    "dep_contracts": dep_contracts,
                    "fields_by_contract_json": json.dumps(fbc),
                    "teams": teams,
                    "alerting_profiles": alerting_profiles,
                },
            )
        raw_yaml = raw_yaml_input
        form_data = yaml_dict_to_form(doc)
    else:
        connections = await _get_connections(db)
        conn_map = connection_id_to_name_map_from_connections(connections)
        doc = form_to_yaml_dict(form_dict, conn_map)
        raw_yaml = dict_to_yaml_string(doc)
        form_data = yaml_dict_to_form(doc)

    contract_id = doc.get("id", "")
    title = doc.get("info", {}).get("title", "")

    if not contract_id:
        errors.append("Contract ID is required.")
    if not title:
        errors.append("Title is required.")

    info = doc.get("info", {}) or {}
    xs = doc.get("x-sraosha", {}) if isinstance(doc.get("x-sraosha"), dict) else {}
    team_id, team_errors = await _resolve_team_id_from_doc(db, xs, info)
    errors.extend(team_errors)

    if not errors:
        existing = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
        if existing.scalar_one_or_none():
            errors.append(f"A contract with ID '{contract_id}' already exists.")

    if errors:
        connections = await _get_connections(db)
        dep_contracts = await _all_contract_ids(db)
        fbc = await _fields_by_contract_map(db)
        teams, alerting_profiles = await _teams_and_alerting_profiles(db)
        return templates.TemplateResponse(
            request,
            "contract_form.html",
            {
                "active_page": "Contracts",
                "mode": "create",
                "form": form_data,
                "raw_yaml": raw_yaml,
                "errors": errors,
                "connections": connections,
                "dep_contracts": dep_contracts,
                "fields_by_contract_json": json.dumps(fbc),
                "teams": teams,
                "alerting_profiles": alerting_profiles,
            },
        )

    alerting_profile_id = await _resolve_alerting_profile_id_from_doc(db, xs)
    await _enrich_doc_x_sraosha(db, doc, team_id, alerting_profile_id)
    raw_yaml = dict_to_yaml_string(doc)

    contract = Contract(
        contract_id=contract_id,
        title=title,
        description=info.get("description"),
        file_path=f"contracts/{contract_id}.yaml",
        team_id=team_id,
        alerting_profile_id=alerting_profile_id,
        raw_yaml=raw_yaml,
        enforcement_mode=xs.get("enforcement_mode", "block"),
    )
    db.add(contract)
    await db.flush()

    return RedirectResponse(url=f"/ui/contracts/{contract_id}", status_code=303)


# ---------------------------------------------------------------------------
# Discover from Database
# ---------------------------------------------------------------------------


@router.get("/contracts/discover", response_class=HTMLResponse)
async def discover_form(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the discover-from-database wizard page."""
    teams, alerting_profiles = await _teams_and_alerting_profiles(db)
    return templates.TemplateResponse(
        request,
        "contract_discover.html",
        {
            "active_page": "Contracts",
            "teams": teams,
            "alerting_profiles": alerting_profiles,
        },
    )


@router.post("/partials/discover-test", response_class=HTMLResponse)
async def partial_discover_test(request: Request):
    """Test a database connection and return a success/error partial."""
    from sraosha.api.introspect import SUPPORTED_TYPES, get_introspector

    form = await request.form()
    server_type = _form_text(form.get("server_type"), "postgres")
    params = {
        "host": _form_text(form.get("host")),
        "port": _form_text(form.get("port")),
        "database": _form_text(form.get("database")),
        "schema": _form_text(form.get("schema"), "public"),
        "user": _form_text(form.get("user")),
        "password": _form_text(form.get("password")),
        "path": _form_text(form.get("path")),
    }

    if server_type not in SUPPORTED_TYPES:
        return HTMLResponse(
            f'<div class="text-sm text-red-600 flex items-center gap-2">'
            f'<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            f'<path stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
            f"Introspection not supported for {server_type}. "
            f"Supported: {', '.join(SUPPORTED_TYPES)}</div>"
        )

    try:
        introspector = get_introspector(server_type, **params)
        ok = introspector.test_connection()
        introspector.close()
    except Exception as exc:
        return HTMLResponse(
            f'<div class="text-sm text-red-600 flex items-center gap-2">'
            f'<svg class="w-4 h-4 flex-shrink-0" fill="none" '
            f'stroke="currentColor" viewBox="0 0 24 24">'
            f'<path stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
            f"Connection failed: {exc}</div>"
        )

    if ok:
        return HTMLResponse(
            '<div class="text-sm text-green-600 flex items-center gap-2">'
            '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" '
            'stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
            "Connection successful</div>"
        )
    return HTMLResponse(
        '<div class="text-sm text-red-600 flex items-center gap-2">'
        '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
        "Connection test returned false</div>"
    )


@router.post("/partials/discover-tables", response_class=HTMLResponse)
async def partial_discover_tables(request: Request):
    """Discover tables from a database and return them as a selectable list."""
    from sraosha.api.introspect import get_introspector

    form = await request.form()
    server_type = _form_text(form.get("server_type"), "postgres")
    schema = _form_text(form.get("schema"), "public") or "public"
    params = {
        "host": _form_text(form.get("host")),
        "port": _form_text(form.get("port")),
        "database": _form_text(form.get("database")),
        "user": _form_text(form.get("user")),
        "password": _form_text(form.get("password")),
        "path": _form_text(form.get("path")),
    }

    try:
        introspector = get_introspector(server_type, **params)
        tables = introspector.discover(schema)
        introspector.close()
    except Exception as exc:
        return HTMLResponse(f'<div class="text-sm text-red-600 p-4">Discovery failed: {exc}</div>')

    if not tables:
        return HTMLResponse(
            '<div class="text-sm text-gray-500 p-4">No tables found in this schema.</div>'
        )

    return templates.TemplateResponse(
        request,
        "partials/discover_table_list.html",
        {
            "tables": tables,
            "schema": schema,
        },
    )


@router.post("/partials/wizard-discover", response_class=HTMLResponse)
async def partial_wizard_discover(request: Request, db: AsyncSession = Depends(get_db)):
    """Discover tables for the wizard (Step 3).

    Accepts either direct connection params or a ``connection_id``
    referencing a saved Connection whose credentials are decrypted
    on-the-fly.
    """
    from sraosha.api.introspect import get_introspector
    from sraosha.crypto import decrypt

    form = await request.form()
    server_type = _form_text(form.get("server_type"), "postgres")
    schema = _form_text(form.get("schema"), "public") or "public"
    connection_id = _form_text(form.get("connection_id"))

    params: dict[str, str] = {}
    if connection_id:
        conn = await db.get(Connection, connection_id)
        if not conn:
            return HTMLResponse('<div class="text-sm text-red-600 p-2">Connection not found.</div>')
        params["host"] = conn.host or ""
        params["port"] = str(conn.port) if conn.port else ""
        params["database"] = conn.database or ""
        params["user"] = conn.username or ""
        params["password"] = decrypt(conn.password_encrypted) if conn.password_encrypted else ""
        params["path"] = conn.path or ""
    else:
        params = {
            "host": _form_text(form.get("host")),
            "port": _form_text(form.get("port")),
            "database": _form_text(form.get("database")),
            "user": _form_text(form.get("user")),
            "password": _form_text(form.get("password")),
            "path": _form_text(form.get("path")),
        }

    try:
        introspector = get_introspector(server_type, **params)
        tables = introspector.discover(schema)
        introspector.close()
    except Exception as exc:
        return HTMLResponse(f'<div class="text-sm text-red-600 p-4">Discovery failed: {exc}</div>')

    if not tables:
        return HTMLResponse(
            '<div class="text-sm text-gray-500 p-4">No tables found in this schema.</div>'
        )

    return templates.TemplateResponse(
        request,
        "partials/wizard_discover_results.html",
        {"tables": tables, "schema": schema},
    )


@router.post("/contracts/discover", response_class=HTMLResponse)
async def discover_generate(request: Request, db: AsyncSession = Depends(get_db)):
    """Generate contracts from discovered tables."""
    from sraosha.api.introspect import _map_type, get_introspector

    form = await request.form()
    form_dict = _multi_items_to_dict(form)
    server_type = form_dict.get("server_type", "postgres")
    schema = form_dict.get("schema", "public") or "public"
    selected_tables = form_dict.get("selected_tables[]", [])
    if isinstance(selected_tables, str):
        selected_tables = [selected_tables]

    owner = form_dict.get("owner", "")
    owner_team = form_dict.get("owner_team", "")
    team_id_sel = _parse_uuid(form_dict.get("team_id"))
    alerting_profile_sel = _parse_uuid(form_dict.get("alerting_profile_id"))

    conn_params = {
        "host": form_dict.get("host", ""),
        "port": form_dict.get("port", ""),
        "database": form_dict.get("database", ""),
        "user": form_dict.get("user", ""),
        "password": form_dict.get("password", ""),
        "path": form_dict.get("path", ""),
    }

    if not selected_tables:
        return RedirectResponse(url="/ui/contracts/discover", status_code=303)

    try:
        introspector = get_introspector(server_type, **conn_params)
    except Exception:
        return RedirectResponse(url="/ui/contracts/discover", status_code=303)

    created = 0
    for table_name in selected_tables:
        try:
            columns = introspector.get_columns(schema, table_name)
        except Exception:
            continue

        contract_id = f"{table_name}-v1"
        title = table_name.replace("_", " ").title()

        fields: dict = {}
        for col in columns:
            fdef: dict = {"type": _map_type(col["data_type"])}
            if not col["is_nullable"]:
                fdef["required"] = True
            fields[col["column_name"]] = fdef

        server_def: dict = {"type": server_type}
        if conn_params.get("host"):
            server_def["host"] = conn_params["host"]
        if conn_params.get("port"):
            try:
                server_def["port"] = int(conn_params["port"])
            except ValueError:
                pass
        if conn_params.get("database"):
            server_def["database"] = conn_params["database"]
        if schema:
            server_def["schema"] = schema
        if conn_params.get("path"):
            server_def["path"] = conn_params["path"]

        doc = {
            "dataContractSpecification": "1.1.0",
            "id": contract_id,
            "info": {
                "title": title,
                "version": "1.0.0",
                "description": f"Auto-discovered from {server_type}://{schema}.{table_name}",
                "owner": owner or owner_team or "",
            },
            "servers": {"production": server_def},
            "models": {table_name: {"type": "table", "fields": fields}},
        }
        xs: dict = {"enforcement_mode": "warn"}
        if team_id_sel:
            xs["team_id"] = str(team_id_sel)
        elif owner_team:
            xs["owner_team"] = owner_team
        if alerting_profile_sel:
            xs["alerting_profile_id"] = str(alerting_profile_sel)
        doc["x-sraosha"] = xs

        from sraosha.api.contract_yaml import dict_to_yaml_string

        info = cast(dict[str, Any], doc["info"])
        xs_raw = doc.get("x-sraosha", {})
        xs2: dict[str, Any] = xs_raw if isinstance(xs_raw, dict) else {}
        team_res, team_errs = await _resolve_team_id_from_doc(db, xs2, info)
        if team_errs:
            continue
        profile_res = await _resolve_alerting_profile_id_from_doc(db, xs2)
        await _enrich_doc_x_sraosha(db, doc, team_res, profile_res)
        raw_yaml = dict_to_yaml_string(doc)

        existing = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
        if existing.scalar_one_or_none():
            continue

        contract = Contract(
            contract_id=contract_id,
            title=title,
            description=info["description"],
            file_path=f"contracts/{contract_id}.yaml",
            team_id=team_res,
            alerting_profile_id=profile_res,
            raw_yaml=raw_yaml,
            enforcement_mode="warn",
        )
        db.add(contract)
        created += 1

    introspector.close()
    if created:
        await db.flush()

    return RedirectResponse(url="/ui/contracts", status_code=303)


# ---------------------------------------------------------------------------
# Run detail
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(
    request: Request,
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid_mod.UUID(run_id)
    except ValueError:
        return HTMLResponse("<h1>Invalid run ID</h1>", status_code=400)

    result = await db.execute(select(ValidationRun).where(ValidationRun.id == uid))
    run = result.scalar_one_or_none()
    if not run:
        return HTMLResponse("<h1>Run not found</h1>", status_code=404)

    contract_result = await db.execute(
        select(Contract).where(Contract.contract_id == run.contract_id)
    )
    contract = contract_result.scalar_one_or_none()

    neighbors = await db.execute(
        select(ValidationRun.id, ValidationRun.run_at)
        .where(ValidationRun.contract_id == run.contract_id)
        .order_by(ValidationRun.run_at.desc())
    )
    ordered = [(str(r[0]), r[1]) for r in neighbors.all()]
    prev_id = next_id = None
    for i, (rid, _) in enumerate(ordered):
        if rid == str(run.id):
            if i + 1 < len(ordered):
                prev_id = ordered[i + 1][0]
            if i > 0:
                next_id = ordered[i - 1][0]
            break

    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "active_page": "Contracts",
            "run": run,
            "contract": contract,
            "prev_run_id": prev_id,
            "next_run_id": next_id,
        },
    )


# ---------------------------------------------------------------------------
# Contract detail (must be after /contracts/new and /contracts/discover)
# ---------------------------------------------------------------------------


@router.get("/contracts/{contract_id}", response_class=HTMLResponse)
async def contract_detail(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Contract)
        .where(Contract.contract_id == contract_id)
        .options(selectinload(Contract.team))
    )
    contract = result.scalar_one_or_none()
    if not contract:
        return HTMLResponse("<h1>Contract not found</h1>", status_code=404)

    runs_result = await db.execute(
        select(ValidationRun)
        .where(ValidationRun.contract_id == contract_id)
        .order_by(ValidationRun.run_at.desc())
        .limit(20)
    )
    runs = runs_result.scalars().all()

    parsed_models = []
    try:
        doc = yaml_string_to_dict(contract.raw_yaml)
        form_data = yaml_dict_to_form(doc)
        parsed_models = form_data.get("models", [])
    except (ValueError, Exception):
        pass

    sched_result = await db.execute(
        select(ValidationSchedule).where(ValidationSchedule.contract_id == contract_id)
    )
    schedule = sched_result.scalar_one_or_none()

    downstream_count = 0
    try:
        analyzer = await _build_analyzer(db)
        downstream_count = len(analyzer.get_downstream(contract_id))
    except Exception:
        downstream_count = 0

    return templates.TemplateResponse(
        request,
        "contract_detail.html",
        {
            "active_page": "Contracts",
            "contract": contract,
            "contract_id": contract_id,
            "runs": runs,
            "parsed_models": parsed_models,
            "schedule": schedule,
            "preset_labels": PRESET_LABELS,
            "downstream_count": downstream_count,
        },
    )


@router.get("/contracts/{contract_id}/edit", response_class=HTMLResponse)
async def contract_edit_form(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Show the edit form pre-populated from the DB."""
    result = await db.execute(
        select(Contract)
        .where(Contract.contract_id == contract_id)
        .options(selectinload(Contract.team), selectinload(Contract.alerting_profile))
    )
    contract = result.scalar_one_or_none()
    if not contract:
        return HTMLResponse("<h1>Contract not found</h1>", status_code=404)

    try:
        doc = yaml_string_to_dict(contract.raw_yaml)
    except ValueError:
        doc = {"id": contract.contract_id, "info": {"title": contract.title}}

    form_data = yaml_dict_to_form(doc)
    form_data["owner_team"] = form_data.get("owner_team") or contract.owner_team or ""
    if contract.team_id:
        form_data["team_id"] = str(contract.team_id)
    if contract.alerting_profile_id:
        form_data["alerting_profile_id"] = str(contract.alerting_profile_id)
    form_data["enforcement_mode"] = form_data.get("enforcement_mode") or contract.enforcement_mode
    connections = await _get_connections(db)
    dep_contracts = await _all_contract_ids(db)
    fbc = await _fields_by_contract_map(db)
    teams, alerting_profiles = await _teams_and_alerting_profiles(db)

    return templates.TemplateResponse(
        request,
        "contract_form.html",
        {
            "active_page": "Contracts",
            "mode": "edit",
            "contract_id": contract_id,
            "form": form_data,
            "raw_yaml": contract.raw_yaml,
            "errors": [],
            "connections": connections,
            "dep_contracts": dep_contracts,
            "fields_by_contract_json": json.dumps(fbc),
            "teams": teams,
            "alerting_profiles": alerting_profiles,
        },
    )


@router.post("/contracts/{contract_id}/edit", response_class=HTMLResponse)
async def contract_update(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle contract update from the form."""
    result = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        return HTMLResponse("<h1>Contract not found</h1>", status_code=404)

    form_dict = _multi_items_to_dict(await request.form())
    raw_yaml_input = form_dict.get("raw_yaml", "").strip()
    errors: list[str] = []

    if raw_yaml_input:
        try:
            doc = yaml_string_to_dict(raw_yaml_input)
        except ValueError as exc:
            errors.append(str(exc))
            form_data = (
                yaml_dict_to_form(yaml_string_to_dict(contract.raw_yaml))
                if contract.raw_yaml
                else _empty_form_data()
            )
            connections = await _get_connections(db)
            dep_contracts = await _all_contract_ids(db)
            fbc = await _fields_by_contract_map(db)
            teams, alerting_profiles = await _teams_and_alerting_profiles(db)
            return templates.TemplateResponse(
                request,
                "contract_form.html",
                {
                    "active_page": "Contracts",
                    "mode": "edit",
                    "contract_id": contract_id,
                    "form": form_data,
                    "raw_yaml": raw_yaml_input,
                    "errors": errors,
                    "connections": connections,
                    "dep_contracts": dep_contracts,
                    "fields_by_contract_json": json.dumps(fbc),
                    "teams": teams,
                    "alerting_profiles": alerting_profiles,
                },
            )
        raw_yaml = raw_yaml_input
        form_data = yaml_dict_to_form(doc)
    else:
        connections = await _get_connections(db)
        conn_map = connection_id_to_name_map_from_connections(connections)
        doc = form_to_yaml_dict(form_dict, conn_map)
        raw_yaml = dict_to_yaml_string(doc)
        form_data = yaml_dict_to_form(doc)

    title = doc.get("info", {}).get("title", "")
    if not title:
        errors.append("Title is required.")

    info = doc.get("info", {}) or {}
    raw_xs = doc.get("x-sraosha")
    xs = raw_xs if isinstance(raw_xs, dict) else {}
    team_id, team_errors = await _resolve_team_id_from_doc(db, xs, info)
    errors.extend(team_errors)

    if errors:
        connections = await _get_connections(db)
        dep_contracts = await _all_contract_ids(db)
        fbc = await _fields_by_contract_map(db)
        teams, alerting_profiles = await _teams_and_alerting_profiles(db)
        return templates.TemplateResponse(
            request,
            "contract_form.html",
            {
                "active_page": "Contracts",
                "mode": "edit",
                "contract_id": contract_id,
                "form": form_data,
                "raw_yaml": raw_yaml,
                "errors": errors,
                "connections": connections,
                "dep_contracts": dep_contracts,
                "fields_by_contract_json": json.dumps(fbc),
                "teams": teams,
                "alerting_profiles": alerting_profiles,
            },
        )

    alerting_profile_id = await _resolve_alerting_profile_id_from_doc(db, xs)
    await _enrich_doc_x_sraosha(db, doc, team_id, alerting_profile_id)
    raw_yaml = dict_to_yaml_string(doc)

    contract.title = title
    contract.description = info.get("description")
    contract.team_id = team_id
    contract.alerting_profile_id = alerting_profile_id
    contract.raw_yaml = raw_yaml
    contract.enforcement_mode = xs.get("enforcement_mode", contract.enforcement_mode)
    contract.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return RedirectResponse(url=f"/ui/contracts/{contract_id}", status_code=303)


@router.delete("/contracts/{contract_id}", response_class=HTMLResponse)
async def contract_delete(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a contract and redirect to the list."""
    result = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        return HTMLResponse("<h1>Contract not found</h1>", status_code=404)

    await db.delete(contract)
    return HTMLResponse(
        status_code=200,
        headers={"HX-Redirect": "/ui/contracts"},
    )


# ---------------------------------------------------------------------------
# htmx partials for contract form
# ---------------------------------------------------------------------------


@router.get("/partials/server-row", response_class=HTMLResponse)
async def partial_server_row(request: Request, idx: int = Query(0)):
    return templates.TemplateResponse(
        request,
        "partials/contract_server_block.html",
        {
            "idx": idx,
            "server": {
                "name": "",
                "type": "postgres",
                "host": "",
                "port": "5432",
                "database": "",
                "schema": "",
                "account": "",
                "warehouse": "",
                "role": "",
                "catalog": "",
                "httpPath": "",
                "project": "",
                "dataset": "",
                "location": "",
                "path": "",
            },
        },
    )


@router.get("/partials/model-block", response_class=HTMLResponse)
async def partial_model_block(request: Request, idx: int = Query(0)):
    return templates.TemplateResponse(
        request,
        "partials/contract_field_row.html",
        {
            "model_idx": idx,
            "model": {"name": "", "type": "table", "fields": []},
            "is_new_model": True,
        },
    )


@router.get("/partials/field-row", response_class=HTMLResponse)
async def partial_field_row(
    request: Request,
    model_name: str = Query(""),
    idx: int = Query(0),
):
    return templates.TemplateResponse(
        request,
        "partials/contract_field_row.html",
        {
            "model_idx": idx,
            "model_name": model_name,
            "field": {"name": "", "type": "text", "required": False, "unique": False},
            "is_new_model": False,
        },
    )


@router.post("/partials/yaml-preview", response_class=HTMLResponse)
async def partial_yaml_preview(request: Request, db: AsyncSession = Depends(get_db)):
    """Convert form data to YAML and return the rendered preview."""
    form_dict = _multi_items_to_dict(await request.form())
    connections = await _get_connections(db)
    conn_map = connection_id_to_name_map_from_connections(connections)
    try:
        doc = form_to_yaml_dict(form_dict, conn_map)
        raw_yaml = dict_to_yaml_string(doc)
        error = None
    except Exception as exc:
        raw_yaml = ""
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "partials/contract_yaml_preview.html",
        {
            "raw_yaml": raw_yaml,
            "error": error,
        },
    )


@router.post("/partials/validate-contract", response_class=HTMLResponse)
async def partial_validate(request: Request, db: AsyncSession = Depends(get_db)):
    """Lightweight YAML validation (structure only)."""
    form_dict = _multi_items_to_dict(await request.form())
    raw_yaml = form_dict.get("raw_yaml", "").strip()
    errors: list[str] = []

    if not raw_yaml:
        try:
            connections = await _get_connections(db)
            conn_map = connection_id_to_name_map_from_connections(connections)
            doc = form_to_yaml_dict(form_dict, conn_map)
            raw_yaml = dict_to_yaml_string(doc)
        except Exception as exc:
            errors.append(f"Form error: {exc}")

    if raw_yaml and not errors:
        try:
            doc = yaml_string_to_dict(raw_yaml)
        except ValueError as exc:
            errors.append(str(exc))

        if not errors:
            if not doc.get("id"):
                errors.append("Missing required field: id")
            if not doc.get("info", {}).get("title"):
                errors.append("Missing required field: info.title")
            if not doc.get("models"):
                errors.append("No models defined")

    return templates.TemplateResponse(
        request,
        "partials/contract_validation_result.html",
        {
            "errors": errors,
            "valid": len(errors) == 0,
        },
    )


@router.get("/partials/delete-modal/{contract_id}", response_class=HTMLResponse)
async def partial_delete_modal(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Contract).where(Contract.contract_id == contract_id))
    contract = result.scalar_one_or_none()
    return templates.TemplateResponse(
        request,
        "partials/contract_delete_modal.html",
        {
            "contract": contract,
        },
    )


# ---------------------------------------------------------------------------
# Data Quality (UI) — HTMX partials
# ---------------------------------------------------------------------------


@router.post("/partials/dq-discover-tables", response_class=HTMLResponse)
async def partial_dq_discover_tables(request: Request, db: AsyncSession = Depends(get_db)):
    """Discover tables from a saved connection for the DQ wizard (Step 2)."""
    from sraosha.api.introspect import get_introspector
    from sraosha.crypto import decrypt

    form = await request.form()
    connection_id = _form_text(form.get("connection_id"))
    schema = _form_text(form.get("schema"), "public") or "public"

    if not connection_id:
        return HTMLResponse(
            '<div class="text-sm text-red-600 dark:text-red-400 p-2">No connection selected.</div>',
            status_code=400,
        )

    conn = await db.get(Connection, connection_id)
    if not conn:
        return HTMLResponse(
            '<div class="text-sm text-red-600 dark:text-red-400 p-2">Connection not found.</div>',
            status_code=404,
        )

    params: dict = {
        "host": conn.host or "",
        "port": str(conn.port) if conn.port else "",
        "database": conn.database or "",
        "user": conn.username or "",
        "password": decrypt(conn.password_encrypted) if conn.password_encrypted else "",
        "path": conn.path or "",
    }

    try:
        introspector = get_introspector(conn.server_type, **params)
        tables = introspector.discover(schema)
        introspector.close()
    except Exception as exc:
        return HTMLResponse(
            f'<div class="text-sm text-red-600 dark:text-red-400 p-4">'
            f"Discovery failed: {exc}</div>",
            status_code=200,
        )

    if not tables:
        return HTMLResponse(
            '<div class="text-sm text-gray-500 dark:text-gray-400 p-4">'
            "No tables found in this schema.</div>",
            status_code=200,
        )

    return templates.TemplateResponse(
        request,
        "partials/dq_table_picker.html",
        {"tables": tables, "schema": schema},
    )


_DQ_TYPE_MAP: dict[str, str] = {
    "int": "integer",
    "int2": "integer",
    "int4": "integer",
    "int8": "integer",
    "smallint": "integer",
    "bigint": "integer",
    "serial": "integer",
    "char": "text",
    "varchar": "text",
    "text": "text",
    "character varying": "text",
    "float": "float",
    "float4": "float",
    "float8": "float",
    "double": "float",
    "double precision": "float",
    "numeric": "float",
    "decimal": "float",
    "real": "float",
    "bool": "boolean",
    "boolean": "boolean",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamp",
    "date": "date",
    "json": "json",
    "jsonb": "json",
    "uuid": "uuid",
    "bytea": "binary",
    "blob": "binary",
}


def _normalize_col_type(raw: str) -> str:
    low = raw.lower().strip()
    for token, mapped in _DQ_TYPE_MAP.items():
        if token in low:
            return mapped
    return "text"


@router.post("/partials/dq-discover-tables-json")
async def partial_dq_discover_tables_json(request: Request, db: AsyncSession = Depends(get_db)):
    """Return discovered tables with columns as JSON for the DQ wizard."""
    from fastapi.responses import JSONResponse

    from sraosha.api.introspect import get_introspector
    from sraosha.crypto import decrypt

    form = await request.form()
    connection_id = _form_text(form.get("connection_id"))
    schema = _form_text(form.get("schema"), "public") or "public"

    if not connection_id:
        return JSONResponse({"error": "No connection selected."}, status_code=400)

    conn = await db.get(Connection, connection_id)
    if not conn:
        return JSONResponse({"error": "Connection not found."}, status_code=404)

    params: dict = {
        "host": conn.host or "",
        "port": str(conn.port) if conn.port else "",
        "database": conn.database or "",
        "user": conn.username or "",
        "password": decrypt(conn.password_encrypted) if conn.password_encrypted else "",
        "path": conn.path or "",
    }

    try:
        introspector = get_introspector(conn.server_type, **params)
        tables = introspector.discover(schema)
        introspector.close()
    except Exception as exc:
        return JSONResponse({"error": f"Discovery failed: {exc}"}, status_code=200)

    if not tables:
        return JSONResponse({"schema": schema, "tables": []})

    out = []
    for t in tables:
        cols = []
        for c in t.get("columns") or []:
            cols.append(
                {
                    "column_name": c["column_name"],
                    "data_type": _normalize_col_type(c.get("data_type", "text")),
                    "is_nullable": c.get("is_nullable", True),
                }
            )
        out.append(
            {
                "table_name": t["table_name"],
                "table_type": t.get("table_type", "table"),
                "columns": cols,
            }
        )

    return JSONResponse({"schema": schema, "tables": out})


@router.post("/partials/dq-generate-check")
async def partial_dq_generate_check(request: Request):
    """Generate a SodaCL snippet from a check template (for the DQ wizard)."""
    import logging

    from fastapi.responses import PlainTextResponse

    log = logging.getLogger("sraosha.dq.generate")

    form = await request.form()
    template_key = (_form_text(form.get("template_key")) or "").strip()
    table = (_form_text(form.get("table")) or "").strip()
    column_raw = _form_text(form.get("column"))
    column = (column_raw.strip() if column_raw not in ("",) else None) or None
    params_raw = _form_text(form.get("params")) or None

    tmpl = DQ_CHECK_TEMPLATES.get(template_key)
    if not tmpl or not table:
        log.debug("dq-generate-check rejected: missing template or table")
        return PlainTextResponse("Missing template_key or table", status_code=400)

    try:
        params = parse_dq_generate_params(params_raw)
    except ValueError as exc:
        log.info("dq-generate-check invalid params: %s", exc)
        return PlainTextResponse(str(exc), status_code=400)

    try:
        snippet = tmpl["generate"](table, column, **params)
    except ValueError as exc:
        log.info("dq-generate-check generation error: %s", exc)
        return PlainTextResponse(str(exc), status_code=400)
    except Exception:
        log.exception("dq-generate-check unexpected error template_key=%s", template_key)
        return PlainTextResponse("Generation failed", status_code=500)

    return PlainTextResponse(snippet)


# ---------------------------------------------------------------------------
# Data Quality (UI)
# ---------------------------------------------------------------------------


@router.get("/data-quality", response_class=HTMLResponse)
async def dq_list_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    q: str = Query("", alias="q"),
    connection: str | None = Query(None),
):
    q = (q or "").strip()
    conn_filter = (connection or "").strip() or None

    result = await db.execute(_list_stmt())
    seen: dict[uuid_mod.UUID, tuple] = {}
    for check, latest, cnt in result.all():
        if check.id not in seen:
            seen[check.id] = (check, latest, cnt)

    healthy = warning = failed = error = 0
    sum_passed = 0
    sum_total = 0
    for _check, latest, _cnt in seen.values():
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

    total_checks = len(seen)
    overall_pass_rate = (sum_passed / sum_total * 100.0) if sum_total > 0 else None

    check_ids = list(seen.keys())
    sched_map: dict[uuid_mod.UUID, DQSchedule] = {}
    if check_ids:
        sr = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id.in_(check_ids)))
        for s in sr.scalars().all():
            sched_map[s.dq_check_id] = s

    conn_ids = {c.connection_id for c, _, _ in seen.values()}
    conns: dict[uuid_mod.UUID, Connection] = {}
    if conn_ids:
        cr = await db.execute(select(Connection).where(Connection.id.in_(conn_ids)))
        for c in cr.scalars().all():
            conns[c.id] = c

    filter_status = (status or "").strip().lower() or None
    selected_connection_id = conn_filter

    checks_out: list[dict] = []
    for check, latest, cnt in seen.values():
        st = latest.status if latest else None
        bucket = _bucket_latest(st)
        if filter_status:
            if filter_status == "healthy" and bucket != "healthy":
                continue
            if filter_status == "warning" and bucket != "warning":
                continue
            if filter_status == "failed" and bucket != "failed":
                continue
            if filter_status == "error" and bucket != "error":
                continue
        if q and q.lower() not in (check.name or "").lower():
            continue
        if conn_filter:
            try:
                cf = uuid_mod.UUID(conn_filter)
            except ValueError:
                cf = None
            if cf is None or check.connection_id != cf:
                continue

        conn = conns.get(check.connection_id)
        sched = sched_map.get(check.id)
        next_run_disp = None
        if sched and sched.is_enabled and sched.next_run_at:
            next_run_disp = sched.next_run_at.strftime("%Y-%m-%d %H:%M UTC")

        checks_out.append(
            {
                "id": str(check.id),
                "name": check.name,
                "description": check.description or "",
                "latest_status": st or "unknown",
                "connection_name": conn.name if conn else "—",
                "connection_type": conn.server_type if conn else "—",
                "tables": list(check.tables or []),
                "run_count": int(cnt or 0),
                "last_run_rel": _relative_time(latest.run_at) if latest else None,
                "next_run_at": next_run_disp,
            }
        )

    checks_out.sort(key=lambda x: (x["name"] or "").lower())

    return templates.TemplateResponse(
        request,
        "dq_list.html",
        {
            "active_page": "Data Quality",
            "summary": {
                "total_checks": total_checks,
                "healthy": healthy,
                "warning": warning,
                "failed": failed,
                "overall_pass_rate": overall_pass_rate,
            },
            "checks": checks_out,
            "filter_status": filter_status,
            "search_query": q,
            "selected_connection_id": selected_connection_id,
            "connections": await _get_connections(db),
        },
    )


@router.get("/data-quality/new", response_class=HTMLResponse)
async def dq_new_form(request: Request, db: AsyncSession = Depends(get_db)):
    connections = await _get_connections(db)
    form_data = {
        "name": "",
        "description": "",
        "connection_id": "",
        "data_source_name": "",
        "tables": [],
        "sodacl_yaml": "",
        "check_categories": [],
        "schedule_enabled": False,
        "interval_preset": "daily",
        "cron_expression": "",
        "run_now": False,
        "schema": "public",
        "team_id": "",
        "alerting_profile_id": "",
    }
    teams, alerting_profiles = await _teams_and_alerting_profiles(db)
    return templates.TemplateResponse(
        request,
        "dq_wizard.html",
        {
            "active_page": "Data Quality",
            "is_edit": False,
            "check": None,
            "form_json": json.dumps(form_data),
            "check_templates_json": json.dumps(_dq_templates_for_js()),
            "connections": connections,
            "teams": teams,
            "alerting_profiles": alerting_profiles,
            "preset_labels": PRESET_LABELS,
            "soda_connector_types": sorted(SODA_CONNECTOR_TYPES),
            "errors": [],
        },
    )


@router.post("/data-quality/create", response_class=HTMLResponse)
async def dq_create(request: Request, db: AsyncSession = Depends(get_db)):
    form = _multi_items_to_dict(await request.form())
    name = (form.get("name") or "").strip()
    description = (form.get("description") or "").strip() or None
    connection_id_raw = (form.get("connection_id") or "").strip()
    sodacl_yaml = (form.get("sodacl_yaml") or "").strip()
    data_source_name_in = (form.get("data_source_name") or "").strip()

    # Accept tables[] (wizard) or tables_csv (legacy fallback)
    tables_raw = form.get("tables[]") or []
    if isinstance(tables_raw, str):
        tables_raw = [tables_raw]
    tables_csv = (form.get("tables_csv") or "").strip()
    if not tables_raw and tables_csv:
        tables_raw = [t.strip() for t in tables_csv.split(",") if t.strip()]

    cats = form.get("check_categories[]") or []
    if isinstance(cats, str):
        cats = [cats]
    schedule_enabled = form.get("schedule_enabled") in ("on", "true", "1")
    interval_preset = (form.get("interval_preset") or "daily").strip()
    cron_expression = (form.get("cron_expression") or "").strip() or None
    run_now = form.get("run_now") in ("on", "true", "1")
    team_id = _parse_uuid(form.get("team_id"))
    alerting_profile_id = _parse_uuid(form.get("alerting_profile_id"))

    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if not connection_id_raw:
        errors.append("Connection is required.")
    if not sodacl_yaml:
        errors.append("SodaCL YAML is required.")

    conn_obj: Connection | None = None
    if connection_id_raw:
        try:
            conn_uuid = uuid_mod.UUID(connection_id_raw)
        except ValueError:
            conn_uuid = None
            errors.append("Invalid connection.")
        if conn_uuid:
            conn_obj = await db.get(Connection, conn_uuid)
            if not conn_obj:
                errors.append("Connection not found.")

    tables: list[str] = [t for t in tables_raw if t]

    ds_name = "data_source"
    if conn_obj:
        ds_name, ds_err = resolve_data_source_name(conn_obj.server_type, data_source_name_in)
        if ds_err:
            errors.append(ds_err)

    if team_id and not await db.get(Team, team_id):
        errors.append("Team not found.")
    if alerting_profile_id and not await db.get(AlertingProfile, alerting_profile_id):
        errors.append("Alerting profile not found.")

    teams_ctx, profiles_ctx = await _teams_and_alerting_profiles(db)
    connections = await _get_connections(db)

    def _error_response(error_list: list[str]):
        form_data = {
            "name": name,
            "description": description or "",
            "connection_id": connection_id_raw,
            "data_source_name": data_source_name_in,
            "tables": tables,
            "sodacl_yaml": sodacl_yaml,
            "check_categories": list(cats),
            "schedule_enabled": schedule_enabled,
            "interval_preset": interval_preset,
            "cron_expression": cron_expression or "",
            "run_now": run_now,
            "schema": "public",
            "team_id": str(team_id) if team_id else "",
            "alerting_profile_id": str(alerting_profile_id) if alerting_profile_id else "",
        }
        return templates.TemplateResponse(
            request,
            "dq_wizard.html",
            {
                "active_page": "Data Quality",
                "is_edit": False,
                "check": None,
                "form_json": json.dumps(form_data),
                "check_templates_json": json.dumps(_dq_templates_for_js()),
                "connections": connections,
                "teams": teams_ctx,
                "alerting_profiles": profiles_ctx,
                "preset_labels": PRESET_LABELS,
                "soda_connector_types": sorted(SODA_CONNECTOR_TYPES),
                "errors": error_list,
            },
        )

    if errors:
        return _error_response(errors)

    dup = await db.execute(select(DQCheck).where(DQCheck.name == name))
    if dup.scalar_one_or_none():
        return _error_response(["A check with this name already exists."])

    assert conn_obj is not None

    check = DQCheck(
        name=name,
        description=description,
        connection_id=conn_obj.id,
        team_id=team_id,
        alerting_profile_id=alerting_profile_id,
        data_source_name=ds_name,
        sodacl_yaml=sodacl_yaml,
        tables=tables,
        check_categories=list(cats),
    )
    db.add(check)
    await db.flush()
    await db.refresh(check)

    if schedule_enabled:
        nr = _compute_next_run(interval_preset, cron_expression)
        db.add(
            DQSchedule(
                dq_check_id=check.id,
                is_enabled=True,
                interval_preset=interval_preset,
                cron_expression=cron_expression,
                next_run_at=nr,
            )
        )
        await db.flush()

    if run_now:
        run_dq_check.delay(str(check.id), "manual")

    return RedirectResponse(
        url=f"/ui/data-quality/{check.id}",
        status_code=303,
    )


@router.get("/data-quality/{check_id}", response_class=HTMLResponse)
async def dq_detail_page(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        return HTMLResponse("<h1>Check not found</h1>", status_code=404)

    conn = await db.get(Connection, check.connection_id)

    runs_result = await db.execute(
        select(DQCheckRun)
        .where(DQCheckRun.dq_check_id == check_id)
        .order_by(DQCheckRun.run_at.desc(), DQCheckRun.id.desc())
        .limit(20)
    )
    runs = list(runs_result.scalars().all())

    latest = runs[0] if runs else None

    sched_result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    schedule = sched_result.scalar_one_or_none()

    total_runs = await db.scalar(
        select(func.count()).select_from(DQCheckRun).where(DQCheckRun.dq_check_id == check_id)
    )
    total_runs = int(total_runs or 0)

    avg_dur = await db.scalar(
        select(func.avg(DQCheckRun.duration_ms)).where(DQCheckRun.dq_check_id == check_id)
    )
    avg_duration_ms = float(avg_dur) if avg_dur is not None else None

    pass_rate = None
    if latest and latest.checks_total > 0:
        pass_rate = round(latest.checks_passed / latest.checks_total * 100.0, 1)

    chart_runs = list(reversed(runs))
    chart_labels = [r.run_at.strftime("%m-%d %H:%M") for r in chart_runs]
    chart_passed = [r.checks_passed for r in chart_runs]
    chart_warned = [r.checks_warned for r in chart_runs]
    chart_failed = [r.checks_failed for r in chart_runs]

    return templates.TemplateResponse(
        request,
        "dq_detail.html",
        {
            "active_page": "Data Quality",
            "check": check,
            "check_id": str(check.id),
            "connection": conn,
            "runs": runs,
            "latest_run": latest,
            "schedule": schedule,
            "stats": {
                "pass_rate": pass_rate,
                "total_runs": total_runs,
                "avg_duration_ms": avg_duration_ms,
            },
            "chart_labels": chart_labels,
            "chart_passed": chart_passed,
            "chart_warned": chart_warned,
            "chart_failed": chart_failed,
            "preset_labels": PRESET_LABELS,
        },
    )


@router.get("/data-quality/{check_id}/edit", response_class=HTMLResponse)
async def dq_edit_form(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        return HTMLResponse("<h1>Check not found</h1>", status_code=404)

    sched_result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    schedule = sched_result.scalar_one_or_none()

    tables = list(check.tables or [])

    conn_for_ds = await db.get(Connection, check.connection_id)
    st = conn_for_ds.server_type if conn_for_ds else ""

    form_data = {
        "name": check.name,
        "description": check.description or "",
        "connection_id": str(check.connection_id),
        "data_source_name": explicit_data_source_for_form(check.data_source_name, st),
        "tables": tables,
        "sodacl_yaml": check.sodacl_yaml,
        "check_categories": list(check.check_categories or []),
        "schedule_enabled": schedule is not None,
        "interval_preset": schedule.interval_preset if schedule else "daily",
        "cron_expression": schedule.cron_expression or "" if schedule else "",
        "run_now": False,
        "schema": "public",
        "team_id": str(check.team_id) if check.team_id else "",
        "alerting_profile_id": str(check.alerting_profile_id) if check.alerting_profile_id else "",
    }

    teams, alerting_profiles = await _teams_and_alerting_profiles(db)
    return templates.TemplateResponse(
        request,
        "dq_wizard.html",
        {
            "active_page": "Data Quality",
            "is_edit": True,
            "check": check,
            "form_json": json.dumps(form_data),
            "check_templates_json": json.dumps(_dq_templates_for_js()),
            "connections": await _get_connections(db),
            "teams": teams,
            "alerting_profiles": alerting_profiles,
            "preset_labels": PRESET_LABELS,
            "soda_connector_types": sorted(SODA_CONNECTOR_TYPES),
            "errors": [],
        },
    )


@router.post("/data-quality/{check_id}/update", response_class=HTMLResponse)
async def dq_update(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        return HTMLResponse("<h1>Check not found</h1>", status_code=404)

    form = _multi_items_to_dict(await request.form())
    name = (form.get("name") or "").strip()
    description = (form.get("description") or "").strip() or None
    connection_id_raw = (form.get("connection_id") or "").strip()
    sodacl_yaml = (form.get("sodacl_yaml") or "").strip()
    data_source_name_in = (form.get("data_source_name") or "").strip()

    # Accept tables[] (wizard) or tables_csv (legacy fallback)
    tables_raw = form.get("tables[]") or []
    if isinstance(tables_raw, str):
        tables_raw = [tables_raw]
    tables_csv = (form.get("tables_csv") or "").strip()
    if not tables_raw and tables_csv:
        tables_raw = [t.strip() for t in tables_csv.split(",") if t.strip()]

    cats = form.get("check_categories[]") or []
    if isinstance(cats, str):
        cats = [cats]
    schedule_enabled = form.get("schedule_enabled") in ("on", "true", "1")
    interval_preset = (form.get("interval_preset") or "daily").strip()
    cron_expression = (form.get("cron_expression") or "").strip() or None
    team_id = _parse_uuid(form.get("team_id"))
    alerting_profile_id = _parse_uuid(form.get("alerting_profile_id"))

    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if not connection_id_raw:
        errors.append("Connection is required.")
    if not sodacl_yaml:
        errors.append("SodaCL YAML is required.")

    if team_id and not await db.get(Team, team_id):
        errors.append("Team not found.")
    if alerting_profile_id and not await db.get(AlertingProfile, alerting_profile_id):
        errors.append("Alerting profile not found.")

    cid = None
    conn_obj = None
    if connection_id_raw:
        try:
            cid = uuid_mod.UUID(connection_id_raw)
        except ValueError:
            errors.append("Invalid connection.")
        if cid and not errors:
            conn_obj = await db.get(Connection, cid)
            if not conn_obj:
                errors.append("Connection not found.")

    tables: list[str] = [t for t in tables_raw if t]

    ds_name = check.data_source_name
    if conn_obj:
        dn, ds_err = resolve_data_source_name(conn_obj.server_type, data_source_name_in)
        if ds_err:
            errors.append(ds_err)
        else:
            ds_name = dn

    connections = await _get_connections(db)
    teams_ctx, profiles_ctx = await _teams_and_alerting_profiles(db)

    def _error_response(error_list: list[str]):
        form_data = {
            "name": name,
            "description": description or "",
            "connection_id": connection_id_raw,
            "data_source_name": data_source_name_in,
            "tables": tables,
            "sodacl_yaml": sodacl_yaml,
            "check_categories": list(cats),
            "schedule_enabled": schedule_enabled,
            "interval_preset": interval_preset,
            "cron_expression": cron_expression or "",
            "run_now": False,
            "schema": "public",
            "team_id": str(team_id) if team_id else "",
            "alerting_profile_id": str(alerting_profile_id) if alerting_profile_id else "",
        }
        return templates.TemplateResponse(
            request,
            "dq_wizard.html",
            {
                "active_page": "Data Quality",
                "is_edit": True,
                "check": check,
                "form_json": json.dumps(form_data),
                "check_templates_json": json.dumps(_dq_templates_for_js()),
                "connections": connections,
                "teams": teams_ctx,
                "alerting_profiles": profiles_ctx,
                "preset_labels": PRESET_LABELS,
                "soda_connector_types": sorted(SODA_CONNECTOR_TYPES),
                "errors": error_list,
            },
        )

    if errors:
        return _error_response(errors)

    if name != check.name:
        dup = await db.execute(select(DQCheck).where(DQCheck.name == name, DQCheck.id != check_id))
        if dup.scalar_one_or_none():
            return _error_response(["A check with this name already exists."])

    check.name = name
    check.description = description
    if cid:
        check.connection_id = cid
    check.team_id = team_id
    check.alerting_profile_id = alerting_profile_id
    check.data_source_name = ds_name
    check.sodacl_yaml = sodacl_yaml
    check.tables = tables
    check.check_categories = list(cats)
    check.updated_at = datetime.now(timezone.utc)

    sched_result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    schedule = sched_result.scalar_one_or_none()

    if schedule_enabled:
        nr = _compute_next_run(interval_preset, cron_expression)
        if schedule:
            schedule.interval_preset = interval_preset
            schedule.cron_expression = cron_expression
            schedule.is_enabled = True
            schedule.next_run_at = nr
            schedule.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                DQSchedule(
                    dq_check_id=check.id,
                    is_enabled=True,
                    interval_preset=interval_preset,
                    cron_expression=cron_expression,
                    next_run_at=nr,
                )
            )
    elif schedule:
        await db.delete(schedule)

    await db.flush()

    return RedirectResponse(url=f"/ui/data-quality/{check_id}", status_code=303)


@router.post("/data-quality/{check_id}/run", response_class=HTMLResponse)
async def dq_trigger_run(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    if not result.scalar_one_or_none():
        return HTMLResponse("Not found", status_code=404)
    run_dq_check.delay(str(check_id), "manual")
    return HTMLResponse(
        "",
        headers={
            "HX-Trigger": json.dumps(
                {
                    "showToast": {
                        "message": "Data quality check queued",
                        "type": "success",
                    },
                }
            ),
        },
    )


@router.post("/data-quality/{check_id}/delete", response_class=HTMLResponse)
async def dq_delete(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        return HTMLResponse("<h1>Check not found</h1>", status_code=404)

    await db.execute(delete(DQCheckRun).where(DQCheckRun.dq_check_id == check_id))
    await db.execute(delete(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    await db.delete(check)
    await db.flush()

    return RedirectResponse(url="/ui/data-quality", status_code=303)


@router.get("/data-quality/{check_id}/runs/{run_id}", response_class=HTMLResponse)
async def dq_run_detail(
    request: Request,
    check_id: uuid_mod.UUID,
    run_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    cr = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    dq_check = cr.scalar_one_or_none()
    if not dq_check:
        return HTMLResponse("<h1>Check not found</h1>", status_code=404)

    rr = await db.execute(
        select(DQCheckRun).where(
            DQCheckRun.id == run_id,
            DQCheckRun.dq_check_id == check_id,
        )
    )
    run = rr.scalar_one_or_none()
    if not run:
        return HTMLResponse("<h1>Run not found</h1>", status_code=404)

    return templates.TemplateResponse(
        request,
        "dq_run_detail.html",
        {
            "active_page": "Data Quality",
            "check": dq_check,
            "run": run,
        },
    )


@router.post("/data-quality/{check_id}/schedule", response_class=HTMLResponse)
async def dq_upsert_schedule(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        return HTMLResponse("Not found", status_code=404)

    form = await request.form()
    raw_preset = (
        _form_text(form.get("preset")) or _form_text(form.get("interval_preset")) or "daily"
    )
    interval_preset = raw_preset.strip()
    cron_expression = (_form_text(form.get("cron_expression")) or "").strip() or None
    is_enabled = form.get("is_enabled") == "on"

    nr = _compute_next_run(interval_preset, cron_expression)

    sched_result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    schedule = sched_result.scalar_one_or_none()

    if schedule:
        schedule.interval_preset = interval_preset
        schedule.cron_expression = cron_expression
        schedule.is_enabled = is_enabled
        schedule.next_run_at = nr
        schedule.updated_at = datetime.now(timezone.utc)
    else:
        schedule = DQSchedule(
            dq_check_id=check_id,
            interval_preset=interval_preset,
            cron_expression=cron_expression,
            is_enabled=is_enabled,
            next_run_at=nr,
        )
        db.add(schedule)

    await db.flush()
    await db.refresh(schedule)

    return templates.TemplateResponse(
        request,
        "partials/dq_schedule_card.html",
        {
            "check_id": str(check_id),
            "schedule": schedule,
            "preset_labels": PRESET_LABELS,
        },
    )


@router.delete("/data-quality/{check_id}/schedule", response_class=HTMLResponse)
async def dq_delete_schedule(
    request: Request,
    check_id: uuid_mod.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DQCheck).where(DQCheck.id == check_id))
    if not result.scalar_one_or_none():
        return HTMLResponse("Not found", status_code=404)

    sched_result = await db.execute(select(DQSchedule).where(DQSchedule.dq_check_id == check_id))
    schedule = sched_result.scalar_one_or_none()
    if schedule:
        await db.delete(schedule)
        await db.flush()

    return templates.TemplateResponse(
        request,
        "partials/dq_schedule_card.html",
        {
            "check_id": str(check_id),
            "schedule": None,
            "preset_labels": PRESET_LABELS,
        },
    )


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

PRESET_SECONDS: dict[str, int] = {
    "hourly": 3600,
    "every_6h": 21600,
    "every_12h": 43200,
    "daily": 86400,
    "weekly": 604800,
}

PRESET_LABELS: dict[str, str] = {
    "hourly": "Every hour",
    "every_6h": "Every 6 hours",
    "every_12h": "Every 12 hours",
    "daily": "Daily",
    "weekly": "Weekly",
    "custom": "Custom (cron)",
}


def _compute_next_run_dt(preset: str, cron_expr: str | None) -> datetime:
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    if preset == "custom" and cron_expr:
        from croniter import croniter

        cron = croniter(cron_expr, now)
        return cron.get_next(datetime).replace(tzinfo=timezone.utc)
    seconds = PRESET_SECONDS.get(preset, 86400)
    return now + timedelta(seconds=seconds)


@router.get("/schedules", response_class=HTMLResponse)
async def schedules_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    type: str = Query("all", alias="type"),
):
    type_filter = (type or "all").strip().lower()
    if type_filter not in ("all", "contract", "data_quality"):
        type_filter = "all"

    status_map = await _contract_run_status_map(db)
    dq_status_map = await _dq_latest_run_status_map(db)

    items: list[dict] = []

    if type_filter in ("all", "contract"):
        query = (
            select(ValidationSchedule, Contract.title, Team.name)
            .join(Contract, Contract.contract_id == ValidationSchedule.contract_id)
            .outerjoin(Team, Contract.team_id == Team.id)
            .order_by(ValidationSchedule.next_run_at.asc())
        )
        result = await db.execute(query)
        for sched, title, owner_team in result.all():
            last_status = status_map.get(sched.contract_id)
            items.append(
                {
                    "schedule_type": "contract",
                    "id": sched.id,
                    "contract_id": sched.contract_id,
                    "contract_title": title,
                    "dq_check_id": None,
                    "dq_check_name": None,
                    "owner_team": owner_team,
                    "is_enabled": sched.is_enabled,
                    "interval_preset": sched.interval_preset,
                    "interval_label": PRESET_LABELS.get(
                        sched.interval_preset, sched.interval_preset
                    ),
                    "cron_expression": sched.cron_expression,
                    "next_run_at": sched.next_run_at,
                    "last_run_at": sched.last_run_at,
                    "last_run_status": last_status,
                }
            )

    if type_filter in ("all", "data_quality"):
        dq_query = (
            select(DQSchedule, DQCheck)
            .join(DQCheck, DQCheck.id == DQSchedule.dq_check_id)
            .options(selectinload(DQCheck.team))
            .order_by(DQSchedule.next_run_at.asc())
        )
        dq_result = await db.execute(dq_query)
        for sched, check in dq_result.all():
            last_st = dq_status_map.get(check.id)
            items.append(
                {
                    "schedule_type": "data_quality",
                    "id": sched.id,
                    "contract_id": None,
                    "contract_title": None,
                    "dq_check_id": check.id,
                    "dq_check_name": check.name,
                    "owner_team": check.owner_team,
                    "is_enabled": sched.is_enabled,
                    "interval_preset": sched.interval_preset,
                    "interval_label": PRESET_LABELS.get(
                        sched.interval_preset, sched.interval_preset
                    ),
                    "cron_expression": sched.cron_expression,
                    "next_run_at": sched.next_run_at,
                    "last_run_at": sched.last_run_at,
                    "last_run_status": last_st,
                }
            )

    if type_filter == "all":
        min_utc = datetime.min.replace(tzinfo=timezone.utc)

        def _sort_key(row: dict) -> tuple:
            n = row["next_run_at"]
            return (n is None, n or min_utc)

        items.sort(key=_sort_key)

    return templates.TemplateResponse(
        request,
        "schedules.html",
        {
            "active_page": "Schedules",
            "schedules": items,
            "preset_labels": PRESET_LABELS,
            "filter_type": type_filter,
        },
    )


@router.post("/schedules/{schedule_id}/toggle", response_class=HTMLResponse)
async def toggle_schedule_enabled(
    request: Request,
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid_mod.UUID(schedule_id)
    except ValueError:
        return HTMLResponse("Invalid schedule", status_code=400)
    sched = await db.get(ValidationSchedule, uid)
    if not sched:
        return HTMLResponse("Not found", status_code=404)
    sched.is_enabled = not sched.is_enabled
    if sched.is_enabled:
        sched.next_run_at = _compute_next_run_dt(
            sched.interval_preset,
            sched.cron_expression,
        )
    sched.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return HTMLResponse(
        "",
        headers={
            "HX-Trigger": json.dumps(
                {
                    "showToast": {
                        "message": "Schedule " + ("enabled" if sched.is_enabled else "paused"),
                        "type": "success",
                    },
                }
            ),
            "HX-Redirect": "/ui/schedules",
        },
    )


@router.post("/contracts/{contract_id}/schedule", response_class=HTMLResponse)
async def dashboard_upsert_schedule(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    interval_preset = _form_text(form.get("interval_preset"), "daily")
    cron_expression = (_form_text(form.get("cron_expression")) or "").strip() or None
    is_enabled = _form_text(form.get("is_enabled"), "on") == "on"

    result = await db.execute(
        select(ValidationSchedule).where(ValidationSchedule.contract_id == contract_id)
    )
    schedule = result.scalar_one_or_none()
    next_run = _compute_next_run_dt(interval_preset, cron_expression)

    if schedule:
        schedule.interval_preset = interval_preset
        schedule.cron_expression = cron_expression
        schedule.is_enabled = is_enabled
        schedule.next_run_at = next_run
        schedule.updated_at = datetime.now(timezone.utc)
    else:
        schedule = ValidationSchedule(
            contract_id=contract_id,
            interval_preset=interval_preset,
            cron_expression=cron_expression,
            is_enabled=is_enabled,
            next_run_at=next_run,
        )
        db.add(schedule)

    await db.flush()
    await db.refresh(schedule)

    return templates.TemplateResponse(
        request,
        "partials/contract_schedule_card.html",
        {
            "contract_id": contract_id,
            "schedule": schedule,
            "preset_labels": PRESET_LABELS,
        },
    )


@router.delete("/contracts/{contract_id}/schedule", response_class=HTMLResponse)
async def dashboard_delete_schedule(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ValidationSchedule).where(ValidationSchedule.contract_id == contract_id)
    )
    schedule = result.scalar_one_or_none()
    if schedule:
        await db.delete(schedule)

    return templates.TemplateResponse(
        request,
        "partials/contract_schedule_card.html",
        {
            "contract_id": contract_id,
            "schedule": None,
            "preset_labels": PRESET_LABELS,
        },
    )


@router.get("/partials/schedule-card/{contract_id}", response_class=HTMLResponse)
async def partial_schedule_card(
    request: Request,
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ValidationSchedule).where(ValidationSchedule.contract_id == contract_id)
    )
    schedule = result.scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "partials/contract_schedule_card.html",
        {
            "contract_id": contract_id,
            "schedule": schedule,
            "preset_labels": PRESET_LABELS,
        },
    )


# ---------------------------------------------------------------------------
# Settings: Teams & Alerting
# ---------------------------------------------------------------------------


@router.get("/settings/teams", response_class=HTMLResponse)
async def settings_teams_list(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Team).order_by(Team.name))
    teams = list(result.scalars().all())
    return templates.TemplateResponse(
        request,
        "settings_teams_list.html",
        {
            "active_page": "Teams",
            "teams": teams,
        },
    )


@router.get("/settings/teams/new", response_class=HTMLResponse)
async def settings_team_new_form(request: Request, db: AsyncSession = Depends(get_db)):
    _, profiles = await _teams_and_alerting_profiles(db)
    return templates.TemplateResponse(
        request,
        "settings_team_form.html",
        {
            "active_page": "Teams",
            "mode": "create",
            "form": {"name": "", "default_alerting_profile_id": ""},
            "errors": [],
            "alerting_profiles": profiles,
        },
    )


@router.post("/settings/teams/new", response_class=HTMLResponse)
async def settings_team_create(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    name = (_form_text(form.get("name")) or "").strip()
    dap = _parse_uuid(_form_text(form.get("default_alerting_profile_id")))
    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if errors:
        _, profiles = await _teams_and_alerting_profiles(db)
        return templates.TemplateResponse(
            request,
            "settings_team_form.html",
            {
                "active_page": "Teams",
                "mode": "create",
                "form": {"name": name, "default_alerting_profile_id": str(dap) if dap else ""},
                "errors": errors,
                "alerting_profiles": profiles,
            },
        )
    team = Team(name=name, default_alerting_profile_id=dap)
    db.add(team)
    try:
        await db.flush()
    except Exception:
        _, profiles = await _teams_and_alerting_profiles(db)
        return templates.TemplateResponse(
            request,
            "settings_team_form.html",
            {
                "active_page": "Teams",
                "mode": "create",
                "form": {"name": name, "default_alerting_profile_id": str(dap) if dap else ""},
                "errors": ["A team with this name may already exist."],
                "alerting_profiles": profiles,
            },
        )
    return RedirectResponse("/ui/settings/teams", status_code=303)


@router.get("/settings/teams/{team_id}/edit", response_class=HTMLResponse)
async def settings_team_edit_form(
    request: Request, team_id: str, db: AsyncSession = Depends(get_db)
):
    uid = _parse_uuid(team_id)
    if not uid:
        return HTMLResponse("Invalid ID", status_code=400)
    team = await db.get(Team, uid)
    if not team:
        return HTMLResponse("Not found", status_code=404)
    _, profiles = await _teams_and_alerting_profiles(db)
    return templates.TemplateResponse(
        request,
        "settings_team_form.html",
        {
            "active_page": "Teams",
            "mode": "edit",
            "team_id": team_id,
            "form": {
                "name": team.name,
                "default_alerting_profile_id": str(team.default_alerting_profile_id)
                if team.default_alerting_profile_id
                else "",
            },
            "errors": [],
            "alerting_profiles": profiles,
        },
    )


@router.post("/settings/teams/{team_id}/edit", response_class=HTMLResponse)
async def settings_team_update(request: Request, team_id: str, db: AsyncSession = Depends(get_db)):
    uid = _parse_uuid(team_id)
    if not uid:
        return HTMLResponse("Invalid ID", status_code=400)
    team = await db.get(Team, uid)
    if not team:
        return HTMLResponse("Not found", status_code=404)
    form = await request.form()
    name = (_form_text(form.get("name")) or "").strip()
    dap = _parse_uuid(_form_text(form.get("default_alerting_profile_id")))
    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if errors:
        _, profiles = await _teams_and_alerting_profiles(db)
        return templates.TemplateResponse(
            request,
            "settings_team_form.html",
            {
                "active_page": "Teams",
                "mode": "edit",
                "team_id": team_id,
                "form": {"name": name, "default_alerting_profile_id": str(dap) if dap else ""},
                "errors": errors,
                "alerting_profiles": profiles,
            },
        )
    team.name = name
    team.default_alerting_profile_id = dap
    try:
        await db.flush()
    except Exception:
        _, profiles = await _teams_and_alerting_profiles(db)
        return templates.TemplateResponse(
            request,
            "settings_team_form.html",
            {
                "active_page": "Teams",
                "mode": "edit",
                "team_id": team_id,
                "form": {"name": name, "default_alerting_profile_id": str(dap) if dap else ""},
                "errors": ["Could not save (duplicate name?)."],
                "alerting_profiles": profiles,
            },
        )
    return RedirectResponse("/ui/settings/teams", status_code=303)


@router.post("/settings/teams/{team_id}/delete", response_class=HTMLResponse)
async def settings_team_delete(team_id: str, db: AsyncSession = Depends(get_db)):
    uid = _parse_uuid(team_id)
    if not uid:
        return RedirectResponse("/ui/settings/teams", status_code=303)
    team = await db.get(Team, uid)
    if team:
        c = await db.scalar(
            select(func.count()).select_from(Contract).where(Contract.team_id == uid)
        )
        d = await db.scalar(select(func.count()).select_from(DQCheck).where(DQCheck.team_id == uid))
        if (c or 0) == 0 and (d or 0) == 0:
            await db.delete(team)
    return RedirectResponse("/ui/settings/teams", status_code=303)


@router.get("/settings/alerting", response_class=HTMLResponse)
async def settings_alerting_list(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AlertingProfile)
        .options(selectinload(AlertingProfile.channels))
        .order_by(AlertingProfile.name)
    )
    profiles = list(result.scalars().unique().all())
    return templates.TemplateResponse(
        request,
        "settings_alerting_list.html",
        {
            "active_page": "Alerting",
            "profiles": profiles,
        },
    )


@router.get("/settings/alerting/new", response_class=HTMLResponse)
async def settings_alerting_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "settings_alerting_form.html",
        {
            "active_page": "Alerting",
            "mode": "create",
            "form": {
                "name": "",
                "description": "",
                "slack_channel": "",
                "email": "",
            },
            "errors": [],
        },
    )


@router.post("/settings/alerting/new", response_class=HTMLResponse)
async def settings_alerting_create(request: Request, db: AsyncSession = Depends(get_db)):
    from sraosha.alerting.channel_types import CHANNEL_EMAIL, CHANNEL_SLACK

    form = await request.form()
    name = (_form_text(form.get("name")) or "").strip()
    description = (_form_text(form.get("description")) or "").strip() or None
    slack_ch = (_form_text(form.get("slack_channel")) or "").strip()
    email = (_form_text(form.get("email")) or "").strip()
    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if not slack_ch and not email:
        errors.append("Provide at least a Slack channel or an email address.")
    if errors:
        return templates.TemplateResponse(
            request,
            "settings_alerting_form.html",
            {
                "active_page": "Alerting",
                "mode": "create",
                "form": {
                    "name": name,
                    "description": description or "",
                    "slack_channel": slack_ch,
                    "email": email,
                },
                "errors": errors,
            },
        )
    profile = AlertingProfile(name=name, description=description)
    db.add(profile)
    await db.flush()
    sort_order = 0
    if slack_ch:
        db.add(
            AlertingProfileChannel(
                alerting_profile_id=profile.id,
                channel_type=CHANNEL_SLACK,
                config={"channel": slack_ch},
                sort_order=sort_order,
            )
        )
        sort_order += 1
    if email:
        db.add(
            AlertingProfileChannel(
                alerting_profile_id=profile.id,
                channel_type=CHANNEL_EMAIL,
                config={"to": [email]},
                sort_order=sort_order,
            )
        )
    await db.flush()
    return RedirectResponse("/ui/settings/alerting", status_code=303)


@router.get("/settings/alerting/{profile_id}/edit", response_class=HTMLResponse)
async def settings_alerting_edit_form(
    request: Request, profile_id: str, db: AsyncSession = Depends(get_db)
):
    uid = _parse_uuid(profile_id)
    if not uid:
        return HTMLResponse("Invalid ID", status_code=400)
    result = await db.execute(
        select(AlertingProfile)
        .where(AlertingProfile.id == uid)
        .options(selectinload(AlertingProfile.channels))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return HTMLResponse("Not found", status_code=404)
    slack_ch = ""
    email = ""
    for ch in profile.channels:
        if ch.channel_type == "slack" and isinstance(ch.config, dict):
            slack_ch = str(ch.config.get("channel") or ch.config.get("slack_channel") or "")
        elif ch.channel_type == "email" and isinstance(ch.config, dict):
            to = ch.config.get("to")
            if isinstance(to, list) and to:
                email = str(to[0])
            elif ch.config.get("email"):
                email = str(ch.config["email"])
    return templates.TemplateResponse(
        request,
        "settings_alerting_form.html",
        {
            "active_page": "Alerting",
            "mode": "edit",
            "profile_id": profile_id,
            "form": {
                "name": profile.name,
                "description": profile.description or "",
                "slack_channel": slack_ch,
                "email": email,
            },
            "errors": [],
        },
    )


@router.post("/settings/alerting/{profile_id}/edit", response_class=HTMLResponse)
async def settings_alerting_update(
    request: Request, profile_id: str, db: AsyncSession = Depends(get_db)
):
    from sraosha.alerting.channel_types import CHANNEL_EMAIL, CHANNEL_SLACK

    uid = _parse_uuid(profile_id)
    if not uid:
        return HTMLResponse("Invalid ID", status_code=400)
    result = await db.execute(
        select(AlertingProfile)
        .where(AlertingProfile.id == uid)
        .options(selectinload(AlertingProfile.channels))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return HTMLResponse("Not found", status_code=404)
    form = await request.form()
    name = (_form_text(form.get("name")) or "").strip()
    description = (_form_text(form.get("description")) or "").strip() or None
    slack_ch = (_form_text(form.get("slack_channel")) or "").strip()
    email = (_form_text(form.get("email")) or "").strip()
    errors: list[str] = []
    if not name:
        errors.append("Name is required.")
    if not slack_ch and not email:
        errors.append("Provide at least a Slack channel or an email address.")
    if errors:
        return templates.TemplateResponse(
            request,
            "settings_alerting_form.html",
            {
                "active_page": "Alerting",
                "mode": "edit",
                "profile_id": profile_id,
                "form": {
                    "name": name,
                    "description": description or "",
                    "slack_channel": slack_ch,
                    "email": email,
                },
                "errors": errors,
            },
        )
    profile.name = name
    profile.description = description
    for ch in list(profile.channels):
        await db.delete(ch)
    await db.flush()
    sort_order = 0
    if slack_ch:
        db.add(
            AlertingProfileChannel(
                alerting_profile_id=profile.id,
                channel_type=CHANNEL_SLACK,
                config={"channel": slack_ch},
                sort_order=sort_order,
            )
        )
        sort_order += 1
    if email:
        db.add(
            AlertingProfileChannel(
                alerting_profile_id=profile.id,
                channel_type=CHANNEL_EMAIL,
                config={"to": [email]},
                sort_order=sort_order,
            )
        )
    await db.flush()
    return RedirectResponse("/ui/settings/alerting", status_code=303)


@router.post("/settings/alerting/{profile_id}/delete", response_class=HTMLResponse)
async def settings_alerting_delete(profile_id: str, db: AsyncSession = Depends(get_db)):
    uid = _parse_uuid(profile_id)
    if not uid:
        return RedirectResponse("/ui/settings/alerting", status_code=303)
    profile = await db.get(AlertingProfile, uid)
    if profile:
        await db.delete(profile)
    return RedirectResponse("/ui/settings/alerting", status_code=303)


# ---------------------------------------------------------------------------
# Connections CRUD
# ---------------------------------------------------------------------------


@router.get("/connections", response_class=HTMLResponse)
async def connections_list(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Connection).order_by(Connection.name))
    connections = list(result.scalars().all())
    cr = await db.execute(select(Contract.contract_id, Contract.raw_yaml))
    contract_rows = cr.all()
    usage: dict[str, int] = {c.name: 0 for c in connections}
    for _cid, raw in contract_rows:
        if not raw:
            continue
        for conn in connections:
            if conn.name and conn.name in raw:
                usage[conn.name] = usage.get(conn.name, 0) + 1
    return templates.TemplateResponse(
        request,
        "connections_list.html",
        {
            "active_page": "Connections",
            "connections": connections,
            "usage_by_name": usage,
        },
    )


@router.get("/connections/new", response_class=HTMLResponse)
async def connection_create_form(request: Request):
    return templates.TemplateResponse(
        request,
        "connection_form.html",
        {
            "active_page": "Connections",
            "mode": "create",
            "form": {
                "name": "",
                "server_type": "postgres",
                "has_password": False,
                "has_token": False,
                "has_service_account_json": False,
            },
            "errors": [],
        },
    )


@router.post("/connections/new", response_class=HTMLResponse)
async def connection_create(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    name = (_form_text(form_data.get("name")) or "").strip()
    server_type = _form_text(form_data.get("server_type"), "postgres")

    errors: list[str] = []
    if not name:
        errors.append("Connection name is required.")

    existing = await db.execute(select(Connection).where(Connection.name == name))
    if existing.scalar_one_or_none():
        errors.append(f"Connection '{name}' already exists.")

    form: dict[str, Any] = dict(form_data)
    form["has_password"] = False
    form["has_token"] = False
    form["has_service_account_json"] = False

    if errors:
        return templates.TemplateResponse(
            request,
            "connection_form.html",
            {
                "active_page": "Connections",
                "mode": "create",
                "form": form,
                "errors": errors,
            },
        )

    from sraosha.crypto import encrypt

    extra = {}
    for key in (
        "region",
        "s3_staging_dir",
        "tenant_id",
        "client_id",
        "client_secret",
        "workspace",
        "lakehouse",
    ):
        val = (_form_text(form_data.get(f"extra_{key}")) or "").strip()
        if val:
            extra[key] = val

    create_port_raw = _form_text(form_data.get("port"))
    conn = Connection(
        name=name,
        server_type=server_type,
        description=_form_text(form_data.get("description")) or None,
        host=_form_text(form_data.get("host")) or None,
        port=int(create_port_raw) if create_port_raw else None,
        database=_form_text(form_data.get("database")) or None,
        schema_name=_form_text(form_data.get("schema_name")) or None,
        account=_form_text(form_data.get("account")) or None,
        warehouse=_form_text(form_data.get("warehouse")) or None,
        role=_form_text(form_data.get("role")) or None,
        catalog=_form_text(form_data.get("catalog")) or None,
        http_path=_form_text(form_data.get("http_path")) or None,
        project=_form_text(form_data.get("project")) or None,
        dataset=_form_text(form_data.get("dataset")) or None,
        location=_form_text(form_data.get("location")) or None,
        path=_form_text(form_data.get("path")) or None,
        username=_form_text(form_data.get("username")) or None,
        password_encrypted=encrypt(_form_text(form_data.get("password")))
        if _form_text(form_data.get("password"))
        else None,
        token_encrypted=encrypt(_form_text(form_data.get("token")))
        if _form_text(form_data.get("token"))
        else None,
        service_account_json_encrypted=(
            encrypt(_form_text(form_data.get("service_account_json")))
            if _form_text(form_data.get("service_account_json"))
            else None
        ),
        extra_params=extra or None,
    )
    db.add(conn)
    await db.flush()
    return RedirectResponse("/ui/connections", status_code=303)


@router.get("/connections/{conn_id}/edit", response_class=HTMLResponse)
async def connection_edit_form(
    request: Request,
    conn_id: str,
    db: AsyncSession = Depends(get_db),
):
    import uuid as uuid_mod

    try:
        uid = uuid_mod.UUID(conn_id)
    except ValueError:
        return HTMLResponse("<h1>Invalid connection ID</h1>", status_code=400)

    result = await db.execute(select(Connection).where(Connection.id == uid))
    conn = result.scalar_one_or_none()
    if not conn:
        return HTMLResponse("<h1>Connection not found</h1>", status_code=404)

    form = {
        "name": conn.name,
        "server_type": conn.server_type,
        "description": conn.description,
        "host": conn.host,
        "port": conn.port,
        "database": conn.database,
        "schema_name": conn.schema_name,
        "account": conn.account,
        "warehouse": conn.warehouse,
        "role": conn.role,
        "catalog": conn.catalog,
        "http_path": conn.http_path,
        "project": conn.project,
        "dataset": conn.dataset,
        "location": conn.location,
        "path": conn.path,
        "username": conn.username,
        "has_password": bool(conn.password_encrypted),
        "has_token": bool(conn.token_encrypted),
        "has_service_account_json": bool(conn.service_account_json_encrypted),
        "extra_params": conn.extra_params or {},
    }

    return templates.TemplateResponse(
        request,
        "connection_form.html",
        {
            "active_page": "Connections",
            "mode": "edit",
            "conn_id": conn_id,
            "form": form,
            "errors": [],
        },
    )


@router.post("/connections/{conn_id}/edit", response_class=HTMLResponse)
async def connection_update(
    request: Request,
    conn_id: str,
    db: AsyncSession = Depends(get_db),
):
    import uuid as uuid_mod

    try:
        uid = uuid_mod.UUID(conn_id)
    except ValueError:
        return HTMLResponse("<h1>Invalid connection ID</h1>", status_code=400)

    result = await db.execute(select(Connection).where(Connection.id == uid))
    conn = result.scalar_one_or_none()
    if not conn:
        return HTMLResponse("<h1>Connection not found</h1>", status_code=404)

    form_data = await request.form()
    name = (_form_text(form_data.get("name")) or "").strip()

    errors: list[str] = []
    if not name:
        errors.append("Connection name is required.")

    if name != conn.name:
        dup = await db.execute(select(Connection).where(Connection.name == name))
        if dup.scalar_one_or_none():
            errors.append(f"Connection '{name}' already exists.")

    form: dict[str, Any] = dict(form_data)
    form["has_password"] = bool(conn.password_encrypted)
    form["has_token"] = bool(conn.token_encrypted)
    form["has_service_account_json"] = bool(conn.service_account_json_encrypted)

    if errors:
        return templates.TemplateResponse(
            request,
            "connection_form.html",
            {
                "active_page": "Connections",
                "mode": "edit",
                "conn_id": conn_id,
                "form": form,
                "errors": errors,
            },
        )

    from sraosha.crypto import encrypt

    conn.name = name
    conn.server_type = _form_text(form_data.get("server_type"), conn.server_type)
    conn.description = _form_text(form_data.get("description")) or None
    conn.host = _form_text(form_data.get("host")) or None
    port_raw = _form_text(form_data.get("port"))
    conn.port = int(port_raw) if port_raw else None
    conn.database = _form_text(form_data.get("database")) or None
    conn.schema_name = _form_text(form_data.get("schema_name")) or None
    conn.account = _form_text(form_data.get("account")) or None
    conn.warehouse = _form_text(form_data.get("warehouse")) or None
    conn.role = _form_text(form_data.get("role")) or None
    conn.catalog = _form_text(form_data.get("catalog")) or None
    conn.http_path = _form_text(form_data.get("http_path")) or None
    conn.project = _form_text(form_data.get("project")) or None
    conn.dataset = _form_text(form_data.get("dataset")) or None
    conn.location = _form_text(form_data.get("location")) or None
    conn.path = _form_text(form_data.get("path")) or None
    conn.username = _form_text(form_data.get("username")) or None

    if _form_text(form_data.get("password")):
        conn.password_encrypted = encrypt(_form_text(form_data.get("password")))
    if _form_text(form_data.get("token")):
        conn.token_encrypted = encrypt(_form_text(form_data.get("token")))
    sa_json = _form_text(form_data.get("service_account_json"))
    if sa_json:
        conn.service_account_json_encrypted = encrypt(sa_json)

    extra = dict(conn.extra_params or {})
    for key in ("region", "s3_staging_dir", "tenant_id", "client_id", "workspace", "lakehouse"):
        val = (_form_text(form_data.get(f"extra_{key}")) or "").strip()
        if val:
            extra[key] = val
        else:
            extra.pop(key, None)
    if (_form_text(form_data.get("extra_client_secret")) or "").strip():
        extra["client_secret"] = _form_text(form_data.get("extra_client_secret")).strip()
    conn.extra_params = extra or None

    conn.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return RedirectResponse("/ui/connections", status_code=303)


@router.post("/connections/{conn_id}/delete")
async def connection_delete(
    request: Request,
    conn_id: str,
    db: AsyncSession = Depends(get_db),
):
    import uuid as uuid_mod

    try:
        uid = uuid_mod.UUID(conn_id)
    except ValueError:
        return RedirectResponse("/ui/connections", status_code=303)

    result = await db.execute(select(Connection).where(Connection.id == uid))
    conn = result.scalar_one_or_none()
    if conn:
        await db.delete(conn)
    return RedirectResponse("/ui/connections", status_code=303)


# API endpoint to fetch connection details for JS auto-population
@router.get("/api/connections/{conn_id}", response_class=HTMLResponse)
async def api_connection_detail(conn_id: str, db: AsyncSession = Depends(get_db)):
    import uuid as uuid_mod

    from fastapi.responses import JSONResponse

    try:
        uid = uuid_mod.UUID(conn_id)
    except ValueError:
        return JSONResponse({"error": "Invalid ID"}, status_code=400)

    result = await db.execute(select(Connection).where(Connection.id == uid))
    conn = result.scalar_one_or_none()
    if not conn:
        return JSONResponse({"error": "Not found"}, status_code=404)

    return JSONResponse(
        {
            "name": conn.name,
            "server_type": conn.server_type,
            "host": conn.host,
            "port": conn.port,
            "database": conn.database,
            "schema_name": conn.schema_name,
            "account": conn.account,
            "warehouse": conn.warehouse,
            "role": conn.role,
            "catalog": conn.catalog,
            "http_path": conn.http_path,
            "project": conn.project,
            "dataset": conn.dataset,
            "location": conn.location,
            "path": conn.path,
        }
    )


def _multi_items_to_dict(form_data) -> dict:
    """Convert Starlette form multi-items into a dict with list values for [] keys."""
    result: dict = {}
    seen_lists: dict[str, list] = {}
    for key, value in form_data.multi_items():
        if key.endswith("[]"):
            seen_lists.setdefault(key, []).append(value)
        else:
            result[key] = value
    result.update(seen_lists)
    return result
