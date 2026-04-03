"""Tests for dashboard team resolution from contract YAML metadata."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sraosha.api.routers.dashboard import _resolve_team_id_from_doc
from sraosha.models.base import Base
from sraosha.models.team import Team

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _create_team_tables(sync_conn) -> None:
    Base.metadata.create_all(sync_conn, tables=[Team.__table__])


def _drop_team_tables(sync_conn) -> None:
    Base.metadata.drop_all(sync_conn, tables=[Team.__table__])


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(_create_team_tables)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(_drop_team_tables)


@pytest.mark.asyncio
async def test_resolve_team_id_invalid_uuid_string() -> None:
    async with TestSessionLocal() as db:
        tid, errs = await _resolve_team_id_from_doc(db, {"team_id": "not-a-uuid"}, {})
        assert tid is None
        assert errs


@pytest.mark.asyncio
async def test_resolve_team_id_unknown_uuid() -> None:
    async with TestSessionLocal() as db:
        missing = uuid.uuid4()
        tid, errs = await _resolve_team_id_from_doc(db, {"team_id": str(missing)}, {})
        assert tid is None
        assert errs


@pytest.mark.asyncio
async def test_resolve_team_id_by_uuid_ok() -> None:
    uid = uuid.uuid4()
    async with TestSessionLocal() as db:
        db.add(Team(id=uid, name="alpha"))
        await db.commit()
    async with TestSessionLocal() as db:
        tid, errs = await _resolve_team_id_from_doc(db, {"team_id": str(uid)}, {})
        assert tid == uid
        assert not errs


@pytest.mark.asyncio
async def test_resolve_team_id_by_owner_name_existing() -> None:
    uid = uuid.uuid4()
    async with TestSessionLocal() as db:
        db.add(Team(id=uid, name="alpha"))
        await db.commit()
    async with TestSessionLocal() as db:
        tid, errs = await _resolve_team_id_from_doc(db, {"owner_team": "alpha"}, {})
        assert tid == uid
        assert not errs


@pytest.mark.asyncio
async def test_resolve_team_id_by_owner_name_missing_team_no_error() -> None:
    async with TestSessionLocal() as db:
        tid, errs = await _resolve_team_id_from_doc(db, {"owner_team": "ghost"}, {})
        assert tid is None
        assert not errs
