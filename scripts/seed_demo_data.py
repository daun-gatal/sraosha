"""
Seed the Sraosha database with rich demo data for the dashboard.

Usage:
    python scripts/seed_demo_data.py          # uses localhost:8000
    python scripts/seed_demo_data.py --api-url http://localhost:8000
"""

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import psycopg2

DB_DSN = "postgresql://sraosha:sraosha@localhost:5432/sraosha"

CONTRACTS = [
    # ── Source: Customers (root node) ──
    {
        "contract_id": "customers-v2",
        "title": "Customers",
        "description": "Customer master data from CRM sync pipeline",
        "owner_team": "team-platform",
        "enforcement_mode": "warn",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: customers-v2
info:
  title: Customers
  version: 2.0.0
  description: Customer master data from CRM sync pipeline
  owner: team-platform
servers:
  production:
    type: postgres
    host: crm-db.company.com
    port: 5432
    database: crm
    schema: public
models:
  customers:
    type: table
    fields:
      customer_id:
        type: text
        required: true
        unique: true
      email:
        type: text
        required: true
      name:
        type: text
        required: true
      segment:
        type: text
      created_at:
        type: timestamp
        required: true
""",
    },
    # ── Source: Products (root node) — Snowflake ──
    {
        "contract_id": "products-v1",
        "title": "Product Catalog",
        "description": "Product catalog from merchandising system (Snowflake)",
        "owner_team": "team-platform",
        "enforcement_mode": "block",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: products-v1
info:
  title: Product Catalog
  version: 1.0.0
  description: Product catalog from merchandising system (Snowflake)
  owner: team-platform
servers:
  production:
    type: snowflake
    account: xy12345.us-east-1
    warehouse: ANALYTICS_WH
    database: CATALOG
    schema: PUBLIC
    role: DATA_READER
models:
  products:
    type: table
    fields:
      product_id:
        type: text
        required: true
        unique: true
      product_name:
        type: text
        required: true
      category:
        type: text
        required: true
      price:
        type: integer
        required: true
""",
    },
    # ── Orders: downstream of customers ──
    {
        "contract_id": "orders-v1",
        "title": "Orders",
        "description": "Order data produced by the checkout service",
        "owner_team": "team-checkout",
        "enforcement_mode": "block",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: orders-v1
info:
  title: Orders
  version: 1.0.0
  description: Order data produced by the checkout service
  owner: team-checkout
servers:
  upstream_customers:
    type: postgres
    host: crm-db.company.com
    port: 5432
    database: crm
    schema: customers
  upstream_products:
    type: postgres
    host: catalog-db.company.com
    port: 5432
    database: catalog
    schema: products
models:
  orders:
    type: table
    fields:
      order_id:
        type: text
        required: true
        unique: true
      customer_id:
        type: text
        required: true
      product_id:
        type: text
        required: true
      order_total:
        type: integer
        required: true
      order_timestamp:
        type: timestamp
        required: true
""",
    },
    # ── Payments: downstream of orders ──
    {
        "contract_id": "payments-v1",
        "title": "Payments",
        "description": "Payment transactions from the billing microservice",
        "owner_team": "team-billing",
        "enforcement_mode": "block",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: payments-v1
info:
  title: Payments
  version: 1.0.0
  description: Payment transactions from the billing microservice
  owner: team-billing
servers:
  upstream_orders:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders
models:
  payments:
    type: table
    fields:
      payment_id:
        type: text
        required: true
        unique: true
      order_id:
        type: text
        required: true
      customer_id:
        type: text
        required: true
      amount:
        type: integer
        required: true
      payment_method:
        type: text
        required: true
      paid_at:
        type: timestamp
        required: true
""",
    },
    # ── Shipping: downstream of orders ──
    {
        "contract_id": "shipping-v1",
        "title": "Shipping",
        "description": "Shipping and delivery data from logistics provider",
        "owner_team": "team-logistics",
        "enforcement_mode": "block",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: shipping-v1
info:
  title: Shipping
  version: 1.0.0
  description: Shipping and delivery data from logistics provider
  owner: team-logistics
servers:
  upstream_orders:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders
models:
  shipments:
    type: table
    fields:
      shipment_id:
        type: text
        required: true
        unique: true
      order_id:
        type: text
        required: true
      customer_id:
        type: text
        required: true
      status:
        type: text
        required: true
      shipped_at:
        type: timestamp
      delivered_at:
        type: timestamp
""",
    },
    # ── Clickstream: downstream of customers — BigQuery ──
    {
        "contract_id": "clickstream-v1",
        "title": "Clickstream Events",
        "description": "User clickstream from web analytics pipeline (BigQuery)",
        "owner_team": "team-analytics",
        "enforcement_mode": "warn",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: clickstream-v1
info:
  title: Clickstream Events
  version: 1.0.0
  description: User clickstream from web analytics pipeline (BigQuery)
  owner: team-analytics
servers:
  production:
    type: bigquery
    project: company-analytics-prod
    dataset: clickstream
    location: us-east1
models:
  events:
    type: table
    fields:
      event_id:
        type: text
        required: true
        unique: true
      customer_id:
        type: text
        required: true
      product_id:
        type: text
      event_type:
        type: text
        required: true
      page_url:
        type: text
      event_timestamp:
        type: timestamp
        required: true
""",
    },
    # ── Returns: downstream of orders + payments ──
    {
        "contract_id": "returns-v1",
        "title": "Returns & Refunds",
        "description": "Product returns and refund processing",
        "owner_team": "team-checkout",
        "enforcement_mode": "block",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: returns-v1
info:
  title: Returns & Refunds
  version: 1.0.0
  description: Product returns and refund processing
  owner: team-checkout
servers:
  upstream_orders:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders
  upstream_payments:
    type: postgres
    host: billing-db.company.com
    port: 5432
    database: billing
    schema: payments
models:
  returns:
    type: table
    fields:
      return_id:
        type: text
        required: true
        unique: true
      order_id:
        type: text
        required: true
      payment_id:
        type: text
        required: true
      customer_id:
        type: text
        required: true
      reason:
        type: text
      refund_amount:
        type: integer
      returned_at:
        type: timestamp
        required: true
""",
    },
    # ── Fulfillment: downstream of shipping + orders ──
    {
        "contract_id": "fulfillment-v1",
        "title": "Fulfillment",
        "description": "End-to-end fulfillment tracking across warehouses",
        "owner_team": "team-logistics",
        "enforcement_mode": "warn",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: fulfillment-v1
info:
  title: Fulfillment
  version: 1.0.0
  description: End-to-end fulfillment tracking across warehouses
  owner: team-logistics
servers:
  upstream_shipments:
    type: postgres
    host: logistics-db.company.com
    port: 5432
    database: logistics
    schema: shipments
  upstream_orders:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders
models:
  fulfillment:
    type: table
    fields:
      fulfillment_id:
        type: text
        required: true
        unique: true
      order_id:
        type: text
        required: true
      shipment_id:
        type: text
        required: true
      customer_id:
        type: text
        required: true
      warehouse:
        type: text
      fulfilled_at:
        type: timestamp
""",
    },
    # ── Analytics: downstream of clickstream + orders — Databricks ──
    {
        "contract_id": "analytics-v1",
        "title": "Customer Analytics",
        "description": "Aggregated customer behavior and purchase analytics (Databricks)",
        "owner_team": "team-analytics",
        "enforcement_mode": "log",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: analytics-v1
info:
  title: Customer Analytics
  version: 1.0.0
  description: Aggregated customer behavior and purchase analytics (Databricks)
  owner: team-analytics
servers:
  production:
    type: databricks
    host: adb-123456789.azuredatabricks.net
    port: 443
    catalog: analytics_catalog
    schema: gold
    httpPath: /sql/1.0/warehouses/abc123def
models:
  customer_analytics:
    type: table
    fields:
      customer_id:
        type: text
        required: true
        unique: true
      total_orders:
        type: integer
      total_spend:
        type: integer
      last_order_timestamp:
        type: timestamp
      event_count:
        type: integer
      segment:
        type: text
""",
    },
]

RUN_PROFILES = {
    "customers-v2": {"pass_rate": 0.92, "num_runs": 35, "checks": 10},
    "products-v1": {"pass_rate": 0.95, "num_runs": 28, "checks": 8},
    "orders-v1": {"pass_rate": 0.72, "num_runs": 30, "checks": 14},
    "payments-v1": {"pass_rate": 0.55, "num_runs": 25, "checks": 12},
    "shipping-v1": {"pass_rate": 0.80, "num_runs": 22, "checks": 10},
    "clickstream-v1": {"pass_rate": 0.65, "num_runs": 28, "checks": 12},
    "returns-v1": {"pass_rate": 0.60, "num_runs": 18, "checks": 14},
    "fulfillment-v1": {"pass_rate": 0.85, "num_runs": 20, "checks": 10},
    "analytics-v1": {"pass_rate": 0.78, "num_runs": 24, "checks": 8},
}

CHECK_TYPES = ["field_is_present", "field_type", "field_required", "field_unique", "general"]


def now_minus(days=0, hours=0, minutes=0):
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)


def _ensure_team_id(api_url: str, cache: dict[str, str], name: str) -> str | None:
    if name in cache:
        return cache[name]
    r = httpx.post(f"{api_url}/api/v1/teams", json={"name": name}, timeout=10.0)
    if r.status_code == 201:
        tid = r.json()["id"]
        cache[name] = tid
        return tid
    if r.status_code == 409:
        lr = httpx.get(f"{api_url}/api/v1/teams", timeout=10.0)
        if lr.status_code != 200:
            return None
        for row in lr.json():
            if row.get("name") == name:
                tid = row["id"]
                cache[name] = tid
                return tid
    return None


def seed_contracts(api_url: str):
    print("Seeding contracts...")
    team_cache: dict[str, str] = {}
    for c in CONTRACTS:
        tid = _ensure_team_id(api_url, team_cache, c["owner_team"])
        resp = httpx.post(
            f"{api_url}/api/v1/contracts",
            json={
                "contract_id": c["contract_id"],
                "title": c["title"],
                "description": c["description"],
                "file_path": f"contracts/{c['contract_id']}.yaml",
                "team_id": tid,
                "alerting_profile_id": None,
                "raw_yaml": c["raw_yaml"],
                "enforcement_mode": c["enforcement_mode"],
            },
            timeout=10.0,
        )
        if resp.status_code == 201:
            print(f"  + {c['contract_id']}")
        elif resp.status_code == 409:
            print(f"  ~ {c['contract_id']} (already exists)")
        else:
            print(f"  ! {c['contract_id']} — {resp.status_code}: {resp.text}")


def seed_runs(conn):
    print("Seeding validation runs...")
    cur = conn.cursor()
    for contract_id, profile in RUN_PROFILES.items():
        for i in range(profile["num_runs"]):
            run_id = str(uuid.uuid4())
            run_at = now_minus(days=profile["num_runs"] - i, hours=random.randint(0, 12))
            passed = random.random() < profile["pass_rate"]
            is_error = not passed and random.random() < 0.15

            if is_error:
                status = "error"
                checks_total = 0
                checks_passed = 0
                checks_failed = 0
                failures = None
                error_message = "Connection timeout to source database"
                duration_ms = None
            elif passed:
                status = "passed"
                checks_total = profile["checks"]
                checks_passed = profile["checks"]
                checks_failed = 0
                failures = None
                error_message = None
                duration_ms = random.randint(50, 500)
            else:
                status = "failed"
                checks_total = profile["checks"]
                num_failed = random.randint(1, max(1, profile["checks"] // 3))
                checks_passed = checks_total - num_failed
                checks_failed = num_failed
                failures = [
                    {
                        "check": random.choice(CHECK_TYPES),
                        "field": random.choice(["id", "name", "status", "created_at", None]),
                        "message": random.choice([
                            "Column not found in source",
                            "Type mismatch: expected integer got text",
                            "Null constraint violated",
                            "Uniqueness check failed",
                            None,
                        ]),
                    }
                    for _ in range(num_failed)
                ]
                error_message = None
                duration_ms = random.randint(100, 2000)

            run_log = _generate_run_log(contract_id, status, checks_total, checks_passed, checks_failed, failures, duration_ms)

            cur.execute(
                """INSERT INTO validation_runs
                   (id, contract_id, status, enforcement_mode,
                    checks_total, checks_passed, checks_failed,
                    failures, server, triggered_by, duration_ms, error_message, run_log, run_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    run_id, contract_id, status,
                    next(c["enforcement_mode"] for c in CONTRACTS if c["contract_id"] == contract_id),
                    checks_total, checks_passed, checks_failed,
                    psycopg2.extras.Json(failures) if failures else None,
                    None,
                    random.choice(["api", "scheduler", "ci"]),
                    duration_ms, error_message, run_log, run_at,
                ),
            )
    conn.commit()
    print(f"  + {sum(p['num_runs'] for p in RUN_PROFILES.values())} runs")


def seed_teams_and_compliance(conn):
    print("Seeding teams and compliance scores...")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM teams ORDER BY name")
    team_ids = {row[1]: str(row[0]) for row in cur.fetchall()}
    if not team_ids:
        print("  (no teams in database; create teams via API or seed contracts first)")
        conn.commit()
        return

    contracts_per_team = {}
    for c in CONTRACTS:
        team = c["owner_team"]
        contracts_per_team.setdefault(team, []).append(c["contract_id"])

    for name, tid in team_ids.items():
        owned = contracts_per_team.get(name, [])
        for period_offset in range(6):
            period_end = now_minus(days=period_offset * 7)
            period_start = period_end - timedelta(days=7)

            total_runs = random.randint(10, 50) * max(1, len(owned))
            pass_rate = random.uniform(0.6, 0.98)
            passed_runs = int(total_runs * pass_rate)
            violations = total_runs - passed_runs
            score = round(pass_rate * 100, 1)

            cur.execute(
                """INSERT INTO compliance_scores
                   (id, team_id, score, total_runs, passed_runs, violations_count,
                    period_start, period_end, computed_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (team_id, period_start, period_end) DO NOTHING""",
                (
                    str(uuid.uuid4()), tid, score, total_runs, passed_runs, violations,
                    period_start, period_end, period_end + timedelta(minutes=5),
                ),
            )

    conn.commit()
    print(f"  + {len(team_ids)} teams, {len(team_ids) * 6} compliance periods")


def _generate_run_log(contract_id, status, checks_total, checks_passed, checks_failed, failures, duration_ms):
    """Generate a realistic-looking validation log."""
    lines = []
    lines.append(f"Starting data contract validation for {contract_id}")
    lines.append(f"Loading contract from file...")
    lines.append(f"Contract loaded successfully")
    lines.append("")

    if status == "error":
        lines.append("ERROR: Connection timeout to source database")
        lines.append("Validation aborted due to connection error")
        return "\n".join(lines)

    lines.append("Starting soda scan...")
    lines.append(f"Running {checks_total} checks against source database")
    lines.append("")

    if failures:
        for f in failures:
            check_name = f.get("check", "unknown_check")
            field = f.get("field", "unknown")
            msg = f.get("message", "Check failed")
            lines.append(f"  FAILED  {contract_id}__{field}__{check_name}: {msg}")
    for i in range(checks_passed):
        lines.append(f"  PASSED  {contract_id}__field_{i}__check_{i}")

    lines.append("")
    lines.append(f"Scan summary:")
    lines.append(f"  {checks_passed}/{checks_total} checks PASSED")
    if checks_failed > 0:
        lines.append(f"  {checks_failed}/{checks_total} checks FAILED")
    if status == "passed":
        lines.append("All is good. No failures. No warnings. No errors.")
    else:
        lines.append(f"Oops! {checks_failed} failure(s) detected.")
    lines.append(f"Finished soda scan in {duration_ms or 0}ms")
    return "\n".join(lines)


SAMPLE_CONNECTIONS = [
    {
        "name": "production",
        "server_type": "postgres",
        "description": "Production PostgreSQL database",
        "host": "postgres",
        "port": 5432,
        "database": "sraosha",
        "schema_name": "public",
        "username": "sraosha",
        "password": "sraosha",
    },
    {
        "name": "staging-snowflake",
        "server_type": "snowflake",
        "description": "Staging Snowflake data warehouse",
        "account": "xy12345.us-east-1",
        "warehouse": "COMPUTE_WH",
        "database": "STAGING_DB",
        "schema_name": "PUBLIC",
        "role": "SYSADMIN",
        "username": "staging_user",
        "password": "staging_pass",
    },
    {
        "name": "analytics-bigquery",
        "server_type": "bigquery",
        "description": "Google BigQuery analytics project",
        "project": "my-analytics-project",
        "dataset": "analytics",
        "location": "us-east1",
    },
]


def seed_connections(conn):
    print("Seeding connections...")
    cur = conn.cursor()

    from cryptography.fernet import Fernet
    import base64, hashlib

    raw_key = "sraosha-dev-key-not-for-production"
    digest = hashlib.sha256(raw_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest[:32])
    f = Fernet(key)

    count = 0
    for c in SAMPLE_CONNECTIONS:
        cur.execute("SELECT 1 FROM connections WHERE name = %s", (c["name"],))
        if cur.fetchone():
            print(f"  ~ {c['name']} (already exists)")
            continue

        pw_enc = f.encrypt(c["password"].encode()).decode() if c.get("password") else None
        tok_enc = f.encrypt(c["token"].encode()).decode() if c.get("token") else None
        sa_enc = f.encrypt(c["service_account_json"].encode()).decode() if c.get("service_account_json") else None

        cur.execute(
            """INSERT INTO connections
               (id, name, server_type, description, host, port, database, schema_name,
                account, warehouse, role, catalog, http_path, project, dataset, location, path,
                username, password_encrypted, token_encrypted, service_account_json_encrypted)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                str(uuid.uuid4()), c["name"], c["server_type"], c.get("description"),
                c.get("host"), c.get("port"), c.get("database"), c.get("schema_name"),
                c.get("account"), c.get("warehouse"), c.get("role"), c.get("catalog"),
                c.get("http_path"), c.get("project"), c.get("dataset"), c.get("location"),
                c.get("path"), c.get("username"), pw_enc, tok_enc, sa_enc,
            ),
        )
        count += 1
        print(f"  + {c['name']}")

    conn.commit()
    print(f"  + {count} connections seeded")


def main():
    parser = argparse.ArgumentParser(description="Seed Sraosha with demo data")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--db-dsn", default=DB_DSN, help="PostgreSQL DSN")
    args = parser.parse_args()

    import psycopg2.extras

    print(f"API: {args.api_url}")
    print(f"DB:  {args.db_dsn}\n")

    seed_contracts(args.api_url)

    conn = psycopg2.connect(args.db_dsn)
    try:
        seed_connections(conn)
        seed_runs(conn)
        seed_teams_and_compliance(conn)
    finally:
        conn.close()

    print("\nDone! Open http://localhost:5173 to see the dashboard.")


if __name__ == "__main__":
    main()
