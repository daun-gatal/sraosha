"""API integration tests using in-memory SQLite + httpx.AsyncClient."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sraosha.api.app import create_app
from sraosha.api.deps import get_db
from sraosha.models.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app = create_app()
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _sample_contract_payload(client) -> dict:
    tr = await client.post("/api/v1/teams", json={"name": "team-checkout"})
    assert tr.status_code == 201
    tid = tr.json()["id"]
    return {
        "contract_id": "orders-v1",
        "title": "Orders",
        "description": "Test contract",
        "file_path": "contracts/orders.yaml",
        "team_id": tid,
        "alerting_profile_id": None,
        "raw_yaml": "id: orders-v1\ninfo:\n  title: Orders",
        "enforcement_mode": "block",
    }


class TestContractsAPI:
    @pytest.mark.asyncio
    async def test_create_contract(self, client):
        payload = await _sample_contract_payload(client)
        resp = await client.post("/api/v1/contracts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["contract_id"] == "orders-v1"
        assert data["title"] == "Orders"

    @pytest.mark.asyncio
    async def test_list_contracts(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.get("/api/v1/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_contract(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.get("/api/v1/contracts/orders-v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contract_id"] == "orders-v1"
        assert "raw_yaml" in data

    @pytest.mark.asyncio
    async def test_get_contract_not_found(self, client):
        resp = await client.get("/api/v1/contracts/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_contract(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.put(
            "/api/v1/contracts/orders-v1",
            json={"title": "Updated Orders", "enforcement_mode": "warn"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Orders"
        assert resp.json()["enforcement_mode"] == "warn"

    @pytest.mark.asyncio
    async def test_delete_contract(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.delete("/api/v1/contracts/orders-v1")
        assert resp.status_code == 204

        resp = await client.get("/api/v1/contracts/orders-v1")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_contract(self, client):
        payload = await _sample_contract_payload(client)
        await client.post("/api/v1/contracts", json=payload)
        resp = await client.post("/api/v1/contracts", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_contract_unknown_team_id(self, client):
        payload = await _sample_contract_payload(client)
        payload["team_id"] = str(uuid.uuid4())
        resp = await client.post("/api/v1/contracts", json=payload)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "team_id not found"


class TestRunsAPI:
    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client):
        resp = await client.get("/api/v1/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_runs_summary_empty(self, client):
        resp = await client.get("/api/v1/runs/summary")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestComplianceAPI:
    @pytest.mark.asyncio
    async def test_list_teams_empty(self, client):
        resp = await client.get("/api/v1/compliance/teams")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_leaderboard_empty(self, client):
        resp = await client.get("/api/v1/compliance/leaderboard")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestImpactAPI:
    @pytest.mark.asyncio
    async def test_graph_empty(self, client):
        resp = await client.get("/api/v1/impact/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    @pytest.mark.asyncio
    async def test_graph_with_contracts(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.get("/api/v1/impact/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "orders-v1"

    @pytest.mark.asyncio
    async def test_lineage_subgraph(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.get(
            "/api/v1/impact/lineage/orders-v1",
            params={"upstream_depth": 1, "downstream_depth": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) >= 1
        assert data["nodes"][0]["id"] == "orders-v1"

    @pytest.mark.asyncio
    async def test_lineage_not_found(self, client):
        resp = await client.get("/api/v1/impact/lineage/missing-contract")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_analyze_impact(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        resp = await client.post(
            "/api/v1/impact/orders-v1/analyze",
            json={"changed_fields": ["customer_id"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contract_id"] == "orders-v1"
        assert data["changed_fields"] == ["customer_id"]
