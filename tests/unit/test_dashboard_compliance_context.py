"""Tests for compliance dashboard context (in-memory SQLite)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sraosha.api.routers.dashboard import _compliance_page_context
from sraosha.models.base import Base
from sraosha.models.contract import Contract
from sraosha.models.run import ValidationRun
from sraosha.models.team import ComplianceScore, Team

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    tables = [
        Team.__table__,
        Contract.__table__,
        ValidationRun.__table__,
        ComplianceScore.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    yield
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=tables))


@pytest.mark.asyncio
async def test_compliance_page_context_lists_all_teams_and_kpis():
    async with TestSessionLocal() as db:
        tid = uuid.uuid4()
        team = Team(id=tid, name="team-alpha")
        db.add(team)
        c = Contract(
            contract_id="orders-v1",
            title="Orders",
            description=None,
            file_path="contracts/orders.yaml",
            team_id=tid,
            raw_yaml="id: orders-v1",
            enforcement_mode="block",
        )
        db.add(c)
        await db.flush()
        now = datetime.now(timezone.utc)
        db.add(
            ValidationRun(
                contract_id="orders-v1",
                status="passed",
                enforcement_mode="block",
                checks_total=1,
                checks_passed=1,
                checks_failed=0,
                run_at=now,
            )
        )
        db.add(
            ComplianceScore(
                team_id=tid,
                score=95.0,
                total_runs=10,
                passed_runs=9,
                violations_count=1,
                period_start=now.date(),
                period_end=now.date(),
                computed_at=now,
            )
        )
        await db.commit()

        ctx = await _compliance_page_context(db)

        assert ctx["has_teams"] is True
        assert ctx["kpis"]["teams_tracked"] == 1
        assert len(ctx["entries"]) == 1
        row = ctx["entries"][0]
        assert row["team_name"] == "team-alpha"
        assert row["score_source"] == "snapshot"
        assert "entries_json" in ctx
        assert "sparkline_points" in row or row.get("sparkline_points") is None
