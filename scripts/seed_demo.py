"""Seed the database with realistic demo data for UI testing.

Run from the project root:
    python scripts/seed_demo.py

Requires DATABASE_URL (sync psycopg2 format) pointing at the Sraosha Postgres.
Defaults to the docker-compose local dev database.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

DB_DSN = "postgresql://sraosha:sraosha@localhost:5432/sraosha"

psycopg2.extras.register_uuid()

# ---------------------------------------------------------------------------
# Contracts (6 realistic data contracts)
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)

CONTRACTS = [
    {
        "contract_id": "orders-v1",
        "title": "Orders",
        "description": "Order data produced by the checkout service",
        "file_path": "contracts/orders-v1.yaml",
        "owner_team": "team-checkout",
        "enforcement_mode": "block",
        "is_active": True,
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: orders-v1
info:
  title: Orders
  version: 1.0.0
  description: Order data produced by the checkout service
  owner: team-checkout
  contact:
    name: Checkout Team
    email: checkout@company.com
servers:
  production:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders
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
      order_total:
        type: integer
        required: true
      order_timestamp:
        type: timestamp
        required: true
x-sraosha:
  owner_team: team-checkout
  enforcement_mode: block
  notify:
    slack_channel: '#data-orders'
    email: checkout@company.com
""",
    },
    {
        "contract_id": "customers-v2",
        "title": "Customer Profiles",
        "description": "Canonical customer dimension table from the CRM pipeline",
        "file_path": "contracts/customers-v2.yaml",
        "owner_team": "team-data-platform",
        "enforcement_mode": "warn",
        "is_active": True,
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: customers-v2
info:
  title: Customer Profiles
  version: 2.0.0
  description: Canonical customer dimension table from the CRM pipeline
  owner: team-data-platform
  contact:
    name: Data Platform Team
    email: data-platform@company.com
servers:
  production:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: customers
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
      full_name:
        type: text
        required: true
      created_at:
        type: timestamp
        required: true
      country_code:
        type: text
        required: false
x-sraosha:
  owner_team: team-data-platform
  enforcement_mode: warn
  notify:
    slack_channel: '#data-platform'
    email: data-platform@company.com
""",
    },
    {
        "contract_id": "payments-v1",
        "title": "Payments Ledger",
        "description": "Payment transaction records from the billing service",
        "file_path": "contracts/payments-v1.yaml",
        "owner_team": "team-billing",
        "enforcement_mode": "block",
        "is_active": True,
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: payments-v1
info:
  title: Payments Ledger
  version: 1.0.0
  description: Payment transaction records from the billing service
  owner: team-billing
  contact:
    name: Billing Team
    email: billing@company.com
servers:
  production:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: payments
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
      amount_cents:
        type: integer
        required: true
      currency:
        type: text
        required: true
      status:
        type: text
        required: true
      paid_at:
        type: timestamp
        required: true
x-sraosha:
  owner_team: team-billing
  enforcement_mode: block
  notify:
    slack_channel: '#billing-alerts'
    email: billing@company.com
""",
    },
    {
        "contract_id": "clickstream-v1",
        "title": "Clickstream Events",
        "description": "Raw clickstream events from the web analytics pipeline",
        "file_path": "contracts/clickstream-v1.yaml",
        "owner_team": "team-analytics",
        "enforcement_mode": "log",
        "is_active": True,
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: clickstream-v1
info:
  title: Clickstream Events
  version: 1.0.0
  description: Raw clickstream events from the web analytics pipeline
  owner: team-analytics
  contact:
    name: Analytics Team
    email: analytics@company.com
servers:
  production:
    type: postgres
    host: analytics-db.company.com
    port: 5432
    database: events
    schema: clickstream
models:
  page_views:
    type: table
    fields:
      event_id:
        type: text
        required: true
        unique: true
      session_id:
        type: text
        required: true
      user_id:
        type: text
        required: false
      page_url:
        type: text
        required: true
      referrer_url:
        type: text
        required: false
      event_timestamp:
        type: timestamp
        required: true
  clicks:
    type: table
    fields:
      click_id:
        type: text
        required: true
        unique: true
      session_id:
        type: text
        required: true
      element_id:
        type: text
        required: true
      clicked_at:
        type: timestamp
        required: true
x-sraosha:
  owner_team: team-analytics
  enforcement_mode: log
  notify:
    slack_channel: '#analytics'
""",
    },
    {
        "contract_id": "inventory-v1",
        "title": "Product Inventory",
        "description": "Real-time product inventory snapshot from the warehouse system",
        "file_path": "contracts/inventory-v1.yaml",
        "owner_team": "team-supply-chain",
        "enforcement_mode": "block",
        "is_active": True,
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: inventory-v1
info:
  title: Product Inventory
  version: 1.0.0
  description: Real-time product inventory snapshot from the warehouse system
  owner: team-supply-chain
  contact:
    name: Supply Chain Team
    email: supply-chain@company.com
servers:
  production:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: inventory
models:
  products:
    type: table
    fields:
      sku:
        type: text
        required: true
        unique: true
      product_name:
        type: text
        required: true
      quantity_on_hand:
        type: integer
        required: true
      reorder_point:
        type: integer
        required: true
      last_restocked_at:
        type: timestamp
        required: false
x-sraosha:
  owner_team: team-supply-chain
  enforcement_mode: block
  notify:
    email: supply-chain@company.com
""",
    },
    {
        "contract_id": "marketing-leads-v1",
        "title": "Marketing Leads",
        "description": "Inbound marketing leads from the CRM integration",
        "file_path": "contracts/marketing-leads-v1.yaml",
        "owner_team": "team-marketing",
        "enforcement_mode": "warn",
        "is_active": False,
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: marketing-leads-v1
info:
  title: Marketing Leads
  version: 1.0.0
  description: Inbound marketing leads from the CRM integration
  owner: team-marketing
  contact:
    name: Marketing Ops
    email: marketing-ops@company.com
servers:
  production:
    type: postgres
    host: crm-db.company.com
    port: 5432
    database: marketing
    schema: leads
models:
  leads:
    type: table
    fields:
      lead_id:
        type: text
        required: true
        unique: true
      email:
        type: text
        required: true
      source:
        type: text
        required: true
      score:
        type: integer
        required: false
      created_at:
        type: timestamp
        required: true
x-sraosha:
  owner_team: team-marketing
  enforcement_mode: warn
  notify:
    slack_channel: '#marketing-data'
""",
    },
]

# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

TEAMS = [
    {"name": "team-checkout", "slack_channel": "#team-checkout", "email": "checkout@company.com"},
    {"name": "team-data-platform", "slack_channel": "#data-platform", "email": "data-platform@company.com"},
    {"name": "team-billing", "slack_channel": "#billing-alerts", "email": "billing@company.com"},
    {"name": "team-analytics", "slack_channel": "#analytics", "email": "analytics@company.com"},
    {"name": "team-supply-chain", "slack_channel": None, "email": "supply-chain@company.com"},
    {"name": "team-marketing", "slack_channel": "#marketing-data", "email": "marketing-ops@company.com"},
]


def main() -> None:
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Clean existing data (order matters for FK constraints)
        for tbl in (
            "alerts",
            "dq_schedules",
            "dq_check_runs",
            "dq_checks",
            "validation_schedules",
            "validation_runs",
            "contracts",
            "compliance_scores",
        ):
            cur.execute(f"DELETE FROM {tbl}")
        cur.execute("UPDATE teams SET default_alerting_profile_id = NULL")
        for tbl in ("teams", "alerting_profile_channels", "alerting_profiles"):
            cur.execute(f"DELETE FROM {tbl}")

        # ----- Alerting profiles + teams (team.default_alerting_profile_id -> profile) -----
        team_ids: dict[str, uuid.UUID] = {}
        profile_ids: dict[str, uuid.UUID] = {}
        for t in TEAMS:
            tid = uuid.uuid4()
            pid = uuid.uuid4()
            team_ids[t["name"]] = tid
            profile_ids[t["name"]] = pid
            t_created = NOW - timedelta(days=90)
            cur.execute(
                """INSERT INTO alerting_profiles (id, name, description, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (pid, f"Default ({t['name']})", None, t_created, t_created),
            )
            sort_order = 0
            if t.get("slack_channel"):
                cur.execute(
                    """INSERT INTO alerting_profile_channels
                       (id, alerting_profile_id, channel_type, config, is_enabled, sort_order,
                        created_at, updated_at)
                       VALUES (%s, %s, %s, %s, true, %s, %s, %s)""",
                    (
                        uuid.uuid4(),
                        pid,
                        "slack",
                        psycopg2.extras.Json({"channel": t["slack_channel"]}),
                        sort_order,
                        t_created,
                        t_created,
                    ),
                )
                sort_order += 1
            if t.get("email"):
                cur.execute(
                    """INSERT INTO alerting_profile_channels
                       (id, alerting_profile_id, channel_type, config, is_enabled, sort_order,
                        created_at, updated_at)
                       VALUES (%s, %s, %s, %s, true, %s, %s, %s)""",
                    (
                        uuid.uuid4(),
                        pid,
                        "email",
                        psycopg2.extras.Json({"to": [t["email"]]}),
                        sort_order,
                        t_created,
                        t_created,
                    ),
                )
                sort_order += 1
            cur.execute(
                """INSERT INTO teams (id, name, default_alerting_profile_id, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (tid, t["name"], pid, t_created, t_created),
            )

        # ----- Contracts -----
        for c in CONTRACTS:
            created_at = NOW - timedelta(days=random.randint(10, 60))
            owner_name = c["owner_team"]
            tid = team_ids.get(owner_name)
            apid = profile_ids.get(owner_name)
            cur.execute(
                """INSERT INTO contracts
                   (id, contract_id, title, description, file_path, team_id, alerting_profile_id,
                    raw_yaml, enforcement_mode, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    uuid.uuid4(),
                    c["contract_id"],
                    c["title"],
                    c["description"],
                    c["file_path"],
                    tid,
                    apid,
                    c["raw_yaml"],
                    c["enforcement_mode"],
                    c["is_active"],
                    created_at,
                    created_at,
                ),
            )

        # ----- Validation Runs -----
        # Generate realistic run histories per contract
        run_configs = {
            "orders-v1":        {"count": 25, "fail_rate": 0.08},
            "customers-v2":     {"count": 20, "fail_rate": 0.15},
            "payments-v1":      {"count": 30, "fail_rate": 0.03},
            "clickstream-v1":   {"count": 18, "fail_rate": 0.22},
            "inventory-v1":     {"count": 12, "fail_rate": 0.0},
            "marketing-leads-v1": {"count": 5, "fail_rate": 0.40},
        }

        run_ids: dict[str, list[uuid.UUID]] = {}

        for cid, cfg in run_configs.items():
            contract = next(c for c in CONTRACTS if c["contract_id"] == cid)
            run_ids[cid] = []
            for i in range(cfg["count"]):
                rid = uuid.uuid4()
                run_ids[cid].append(rid)
                run_at = NOW - timedelta(hours=(cfg["count"] - i) * 6, minutes=random.randint(0, 30))
                failed = random.random() < cfg["fail_rate"]
                checks_total = random.randint(8, 15)
                checks_failed = random.randint(1, 3) if failed else 0
                checks_passed = checks_total - checks_failed

                if failed:
                    status = "failed"
                    failures = [{"check": "schema_compliance", "message": f"Column type mismatch in table"}]
                elif random.random() < 0.03:
                    status = "error"
                    failures = None
                else:
                    status = "passed"
                    failures = None

                cur.execute(
                    """INSERT INTO validation_runs
                       (id, contract_id, status, enforcement_mode,
                        checks_total, checks_passed, checks_failed,
                        failures, server, triggered_by, duration_ms, error_message, run_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        rid, cid, status, contract["enforcement_mode"],
                        checks_total, checks_passed, checks_failed,
                        psycopg2.extras.Json(failures) if failures else None,
                        "production", random.choice(["scheduler", "ci-pipeline", "manual"]),
                        random.randint(200, 3500),
                        "Connection timeout" if status == "error" else None,
                        run_at,
                    ),
                )

        # ----- Compliance Scores -----
        score_data = {
            "team-checkout":      {"score": 94.5, "total": 25, "passed": 23, "violations": 2},
            "team-data-platform": {"score": 87.0, "total": 20, "passed": 17, "violations": 3},
            "team-billing":       {"score": 98.2, "total": 30, "passed": 29, "violations": 1},
            "team-analytics":     {"score": 78.5, "total": 18, "passed": 14, "violations": 4},
            "team-supply-chain":  {"score": 100.0, "total": 12, "passed": 12, "violations": 0},
            "team-marketing":     {"score": 60.0, "total": 5, "passed": 3, "violations": 2},
        }

        period_start = date(2026, 3, 1)
        period_end = date(2026, 3, 29)

        for team_name, sd in score_data.items():
            cur.execute(
                """INSERT INTO compliance_scores
                   (id, team_id, score, total_runs, passed_runs,
                    violations_count, period_start, period_end, computed_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    uuid.uuid4(), team_ids[team_name],
                    sd["score"], sd["total"], sd["passed"],
                    sd["violations"], period_start, period_end, NOW,
                ),
            )

        # ----- Validation Schedules -----
        schedule_configs = [
            ("orders-v1",    "hourly",   None),
            ("customers-v2", "daily",    None),
            ("payments-v1",  "every_6h", None),
            ("clickstream-v1", "custom", "0 */4 * * *"),
        ]

        for cid, preset, cron_expr in schedule_configs:
            if preset == "custom" and cron_expr:
                from croniter import croniter

                next_run = croniter(cron_expr, NOW).get_next(datetime).replace(tzinfo=timezone.utc)
            else:
                interval = {
                    "hourly": 3600, "every_6h": 21600, "every_12h": 43200,
                    "daily": 86400, "weekly": 604800,
                }.get(preset, 86400)
                next_run = NOW + timedelta(seconds=interval)

            last_run = NOW - timedelta(hours=random.randint(1, 12))

            cur.execute(
                """INSERT INTO validation_schedules
                   (id, contract_id, is_enabled, interval_preset,
                    cron_expression, next_run_at, last_run_at, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    uuid.uuid4(), cid, True, preset,
                    cron_expr, next_run, last_run, NOW, NOW,
                ),
            )

        conn.commit()
        print("Seed data inserted successfully.")
        print(f"  - {len(CONTRACTS)} contracts")
        print(f"  - {len(TEAMS)} teams")
        print(f"  - {sum(c['count'] for c in run_configs.values())} validation runs")
        print(f"  - {len(score_data)} compliance scores")
        print(f"  - {len(schedule_configs)} validation schedules")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
