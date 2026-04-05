"""API integration tests using in-memory SQLite + httpx.AsyncClient."""

import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sraosha.api.app import create_app
from sraosha.api.deps import get_db
from sraosha.models.alert import Alert
from sraosha.models.base import Base
from sraosha.models.connection import Connection
from sraosha.models.dq_run import DQCheckRun
from sraosha.models.run import ValidationRun

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
    async def test_create_contract_default_file_path_when_omitted(self, client):
        tr = await client.post("/api/v1/teams", json={"name": "team-fp-default"})
        assert tr.status_code == 201
        tid = tr.json()["id"]
        payload = {
            "contract_id": "my/weird-id",
            "title": "FP",
            "description": None,
            "team_id": tid,
            "alerting_profile_id": None,
            "raw_yaml": "id: my/weird-id\ninfo:\n  title: FP",
            "enforcement_mode": "block",
        }
        resp = await client.post("/api/v1/contracts", json=payload)
        assert resp.status_code == 201
        assert resp.json()["file_path"] == "contracts/my_weird-id.yaml"

    @pytest.mark.asyncio
    async def test_get_contract_includes_parsed_versions(self, client):
        tr = await client.post("/api/v1/teams", json={"name": "team-ver"})
        assert tr.status_code == 201
        tid = tr.json()["id"]
        raw = """dataContractSpecification: "1.0.0"
id: orders-v1
info:
  title: Orders
  version: "3.2.1"
"""
        resp = await client.post(
            "/api/v1/contracts",
            json={
                "contract_id": "orders-v1",
                "title": "Orders",
                "description": None,
                "file_path": "contracts/orders.yaml",
                "team_id": tid,
                "alerting_profile_id": None,
                "raw_yaml": raw,
                "enforcement_mode": "block",
            },
        )
        assert resp.status_code == 201
        detail = await client.get("/api/v1/contracts/orders-v1")
        assert detail.status_code == 200
        data = detail.json()
        assert data["spec_version"] == "1.0.0"
        assert data["info_version"] == "3.2.1"

    @pytest.mark.asyncio
    async def test_update_contract_merges_spec_and_info_version(self, client):
        await client.post("/api/v1/contracts", json=await _sample_contract_payload(client))
        yaml_before = """dataContractSpecification: "1.0.0"
id: orders-v1
info:
  title: Orders
  version: "1.0.0"
"""
        resp = await client.put(
            "/api/v1/contracts/orders-v1",
            json={
                "raw_yaml": yaml_before,
                "spec_version": "1.2.0",
                "info_version": "2.0.0",
            },
        )
        assert resp.status_code == 200
        detail = await client.get("/api/v1/contracts/orders-v1")
        data = detail.json()
        assert data["spec_version"] == "1.2.0"
        assert data["info_version"] == "2.0.0"
        assert "1.2.0" in data["raw_yaml"]
        assert "2.0.0" in data["raw_yaml"]

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
    async def test_delete_contract_removes_schedules_runs_and_alerts(self, client):
        tr = await client.post("/api/v1/teams", json={"name": "team-del-deps"})
        assert tr.status_code == 201
        tid = tr.json()["id"]
        payload = {
            "contract_id": "dep-contract",
            "title": "Dep",
            "description": None,
            "file_path": "contracts/dep.yaml",
            "team_id": tid,
            "alerting_profile_id": None,
            "raw_yaml": "id: dep-contract\ninfo:\n  title: Dep",
            "enforcement_mode": "block",
        }
        assert (await client.post("/api/v1/contracts", json=payload)).status_code == 201
        sch = await client.post(
            "/api/v1/schedules/contracts/dep-contract/schedule",
            json={"interval_preset": "daily", "cron_expression": None, "is_enabled": True},
        )
        assert sch.status_code == 200

        async with TestSessionLocal() as session:
            session.add(
                ValidationRun(
                    contract_id="dep-contract",
                    status="passed",
                    enforcement_mode="block",
                    checks_total=1,
                    checks_passed=1,
                    checks_failed=0,
                    triggered_by="test",
                )
            )
            session.add(
                Alert(
                    contract_id="dep-contract",
                    alert_type="test",
                    channel_type="email",
                    payload={"x": 1},
                )
            )
            await session.commit()

        resp = await client.delete("/api/v1/contracts/dep-contract")
        assert resp.status_code == 204
        assert (await client.get("/api/v1/contracts/dep-contract")).status_code == 404

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


class TestConnectionsAPI:
    @pytest.mark.asyncio
    async def test_list_connections_empty(self, client):
        resp = await client.get("/api/v1/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_connection_not_found(self, client):
        resp = await client.get(f"/api/v1/connections/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_connection_invalid_id(self, client):
        resp = await client.get("/api/v1/connections/not-a-uuid")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_and_get_connection(self, client):
        async with TestSessionLocal() as session:
            c = Connection(name="dq-test-conn", server_type="postgres", host="127.0.0.1")
            session.add(c)
            await session.commit()
            await session.refresh(c)
            cid = str(c.id)

        resp = await client.get("/api/v1/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "dq-test-conn"
        assert data["items"][0]["server_type"] == "postgres"
        assert data["items"][0]["has_password"] is False

        resp = await client.get(f"/api/v1/connections/{cid}")
        assert resp.status_code == 200
        one = resp.json()
        assert one["id"] == cid
        assert one["name"] == "dq-test-conn"

    @pytest.mark.asyncio
    async def test_create_connection(self, client):
        resp = await client.post(
            "/api/v1/connections",
            json={
                "name": "api-created",
                "server_type": "PostgreSQL",
                "host": "127.0.0.1",
                "port": 5432,
                "database": "db",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api-created"
        assert data["server_type"] == "postgres"
        assert data["has_password"] is False

    @pytest.mark.asyncio
    async def test_create_connection_with_password(self, client):
        resp = await client.post(
            "/api/v1/connections",
            json={
                "name": "with-secret",
                "server_type": "postgres",
                "password": "s3cret",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["has_password"] is True

    @pytest.mark.asyncio
    async def test_create_connection_duplicate_name(self, client):
        await client.post(
            "/api/v1/connections",
            json={"name": "dup-conn", "server_type": "postgres"},
        )
        resp = await client.post(
            "/api/v1/connections",
            json={"name": "dup-conn", "server_type": "postgres"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_connection_rejects_unknown_server_type(self, client):
        resp = await client.post(
            "/api/v1/connections",
            json={"name": "bad-st", "server_type": "not_a_real_engine"},
        )
        assert resp.status_code == 400
        assert "unsupported" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_connection_mysql(self, client):
        resp = await client.post(
            "/api/v1/connections",
            json={"name": "mysql-conn", "server_type": "mysql", "host": "127.0.0.1"},
        )
        assert resp.status_code == 201
        assert resp.json()["server_type"] == "mysql"

    @pytest.mark.asyncio
    async def test_cloudsql_alias_normalizes_to_postgres(self, client):
        resp = await client.post(
            "/api/v1/connections",
            json={"name": "legacy-cloudsql", "server_type": "cloudsql"},
        )
        assert resp.status_code == 201
        assert resp.json()["server_type"] == "postgres"

    @pytest.mark.asyncio
    async def test_patch_connection(self, client):
        r = await client.post(
            "/api/v1/connections",
            json={"name": "patch-me", "server_type": "postgres", "host": "a"},
        )
        cid = r.json()["id"]
        resp = await client.patch(
            f"/api/v1/connections/{cid}",
            json={"host": "b", "database": "x"},
        )
        assert resp.status_code == 200
        assert resp.json()["host"] == "b"
        assert resp.json()["database"] == "x"

    @pytest.mark.asyncio
    async def test_delete_connection_blocked_by_dq(self, client):
        r = await client.post(
            "/api/v1/connections",
            json={"name": "dq-block", "server_type": "postgres"},
        )
        cid = r.json()["id"]
        dq = await client.post(
            "/api/v1/data-quality",
            json={
                "name": "check-block-del",
                "connection_id": cid,
                "data_source_name": "postgres",
                "sodacl_yaml": "checks for t:\n  - row_count > 0\n",
            },
        )
        assert dq.status_code == 201
        resp = await client.delete(f"/api/v1/connections/{cid}")
        assert resp.status_code == 409
        assert "data quality" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_connection_ok(self, client):
        r = await client.post(
            "/api/v1/connections",
            json={"name": "del-ok", "server_type": "postgres"},
        )
        cid = r.json()["id"]
        resp = await client.delete(f"/api/v1/connections/{cid}")
        assert resp.status_code == 204
        assert (await client.get(f"/api/v1/connections/{cid}")).status_code == 404


class TestRunsAPI:
    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client):
        resp = await client.get("/api/v1/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_dq_runs_global_empty(self, client):
        resp = await client.get("/api/v1/runs/dq")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_dq_runs_global_with_run(self, client):
        r = await client.post(
            "/api/v1/connections",
            json={"name": "dq-runs-feed", "server_type": "postgres"},
        )
        cid = r.json()["id"]
        dq = await client.post(
            "/api/v1/data-quality",
            json={
                "name": "check-feed",
                "connection_id": cid,
                "data_source_name": "postgres",
                "sodacl_yaml": "checks for t:\n  - row_count > 0\n",
            },
        )
        assert dq.status_code == 201
        check_id = dq.json()["id"]

        async with TestSessionLocal() as session:
            run = DQCheckRun(
                dq_check_id=uuid.UUID(check_id),
                status="passed",
                checks_total=1,
                checks_passed=1,
                checks_warned=0,
                checks_failed=0,
                run_log="ok",
                triggered_by="manual",
            )
            session.add(run)
            await session.commit()

        resp = await client.get("/api/v1/runs/dq")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["dq_check_name"] == "check-feed"
        assert data["items"][0]["status"] == "passed"
        assert data["items"][0]["dq_check_id"] == check_id

    @pytest.mark.asyncio
    async def test_runs_summary_empty(self, client):
        resp = await client.get("/api/v1/runs/summary")
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestConnectionIntrospectionAPI:
    @pytest.mark.asyncio
    async def test_list_tables_mocked(self, client):
        async with TestSessionLocal() as session:
            c = Connection(name="introspect-conn", server_type="postgres", host="127.0.0.1")
            session.add(c)
            await session.commit()
            await session.refresh(c)
            cid = str(c.id)
        fake = [{"table_name": "orders", "table_type": "table"}]
        with patch(
            "sraosha.api.routers.connections.list_tables_sync",
            return_value=("public", fake),
        ):
            resp = await client.get(f"/api/v1/connections/{cid}/tables")
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_name"] == "public"
        assert data["items"][0]["name"] == "orders"
        assert data["items"][0]["kind"] == "table"

    @pytest.mark.asyncio
    async def test_list_columns_mocked(self, client):
        async with TestSessionLocal() as session:
            c = Connection(name="introspect-conn2", server_type="postgres", host="127.0.0.1")
            session.add(c)
            await session.commit()
            await session.refresh(c)
            cid = str(c.id)
        cols = [
            {
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": False,
                "ordinal_position": 1,
            },
        ]
        with patch(
            "sraosha.api.routers.connections.list_columns_sync",
            return_value=("public", cols),
        ):
            resp = await client.get(f"/api/v1/connections/{cid}/tables/public/orders/columns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["table_name"] == "orders"
        assert data["items"][0]["name"] == "id"
        assert data["items"][0]["suggested_field_type"] == "integer"

    @pytest.mark.asyncio
    async def test_list_columns_empty_schema_path_segment(self, client):
        """Empty schema cannot appear as a URL path segment; client sends __sraosha_empty__."""
        async with TestSessionLocal() as session:
            c = Connection(name="introspect-conn3", server_type="mysql", host="127.0.0.1")
            session.add(c)
            await session.commit()
            await session.refresh(c)
            cid = str(c.id)
        cols = [
            {
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": False,
                "ordinal_position": 1,
            },
        ]
        with patch(
            "sraosha.api.routers.connections.list_columns_sync",
            return_value=("", cols),
        ) as mock_sync:
            resp = await client.get(
                f"/api/v1/connections/{cid}/tables/__sraosha_empty__/employees/columns"
            )
        assert resp.status_code == 200
        assert mock_sync.call_args[0][1] == ""


class TestContractPreviewAPI:
    @pytest.mark.asyncio
    async def test_preview_yaml(self, client):
        tr = await client.post("/api/v1/teams", json={"name": "team-preview"})
        assert tr.status_code == 201
        tid = tr.json()["id"]
        async with TestSessionLocal() as session:
            c = Connection(
                name="cprev",
                server_type="postgres",
                host="db.example.com",
                port=5432,
                database="warehouse",
                schema_name="public",
                username="u",
            )
            session.add(c)
            await session.commit()
            await session.refresh(c)
            cid = str(c.id)
        resp = await client.post(
            "/api/v1/contracts/preview-yaml",
            json={
                "connection_id": cid,
                "contract_id": "orders-v1",
                "title": "Orders",
                "table_name": "orders",
                "schema_name": "public",
                "columns": [{"name": "order_id", "field_type": "text", "required": True}],
                "team_id": tid,
            },
        )
        assert resp.status_code == 200
        y = resp.json()["raw_yaml"]
        assert "orders-v1" in y
        assert "orders" in y
        assert "order_id" in y


class TestDQTemplateAPI:
    @pytest.mark.asyncio
    async def test_check_templates(self, client):
        resp = await client.get("/api/v1/data-quality/check-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        keys = {x["key"] for x in data["items"]}
        assert "volume" in keys

    @pytest.mark.asyncio
    async def test_preview_sodacl(self, client):
        resp = await client.post(
            "/api/v1/data-quality/preview-sodacl",
            json={"template_key": "volume", "table": "orders", "params": {}},
        )
        assert resp.status_code == 200
        assert "row_count" in resp.json()["sodacl_yaml"]
