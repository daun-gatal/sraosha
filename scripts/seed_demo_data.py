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
    # ── Source: Products (root node) ──
    {
        "contract_id": "products-v1",
        "title": "Product Catalog",
        "description": "Product catalog from merchandising system",
        "owner_team": "team-platform",
        "enforcement_mode": "block",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: products-v1
info:
  title: Product Catalog
  version: 1.0.0
  description: Product catalog from merchandising system
  owner: team-platform
servers:
  production:
    type: postgres
    host: catalog-db.company.com
    port: 5432
    database: catalog
    schema: public
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
    # ── Clickstream: downstream of customers ──
    {
        "contract_id": "clickstream-v1",
        "title": "Clickstream Events",
        "description": "User clickstream from web analytics pipeline",
        "owner_team": "team-analytics",
        "enforcement_mode": "warn",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: clickstream-v1
info:
  title: Clickstream Events
  version: 1.0.0
  description: User clickstream from web analytics pipeline
  owner: team-analytics
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
    # ── Analytics: downstream of clickstream + orders (aggregation layer) ──
    {
        "contract_id": "analytics-v1",
        "title": "Customer Analytics",
        "description": "Aggregated customer behavior and purchase analytics",
        "owner_team": "team-analytics",
        "enforcement_mode": "log",
        "raw_yaml": """\
dataContractSpecification: 1.1.0
id: analytics-v1
info:
  title: Customer Analytics
  version: 1.0.0
  description: Aggregated customer behavior and purchase analytics
  owner: team-analytics
servers:
  upstream_events:
    type: postgres
    host: analytics-db.company.com
    port: 5432
    database: analytics
    schema: events
  upstream_orders:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders
  upstream_customers:
    type: postgres
    host: crm-db.company.com
    port: 5432
    database: crm
    schema: customers
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

TEAM_NAMES = ["team-checkout", "team-platform", "team-billing", "team-logistics", "team-analytics"]

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

DRIFT_SPECS = [
    ("customers-v2", "null_rate", "customers", "email", 0.01, 0.03),
    ("customers-v2", "freshness_hours", "customers", None, 12.0, 24.0),
    ("customers-v2", "row_count_delta", "customers", None, 0.10, 0.30),
    ("products-v1", "null_rate", "products", "category", 0.005, 0.02),
    ("orders-v1", "null_rate", "orders", "customer_id", 0.02, 0.05),
    ("orders-v1", "row_count_delta", "orders", None, 0.20, 0.50),
    ("orders-v1", "null_rate", "orders", "product_id", 0.01, 0.04),
    ("payments-v1", "null_rate", "payments", "payment_method", 0.005, 0.02),
    ("payments-v1", "row_count_delta", "payments", None, 0.15, 0.40),
    ("shipping-v1", "null_rate", "shipments", "delivered_at", 0.10, 0.25),
    ("shipping-v1", "freshness_hours", "shipments", None, 6.0, 12.0),
    ("clickstream-v1", "null_rate", "events", "page_url", 0.05, 0.10),
    ("clickstream-v1", "row_count_delta", "events", None, 0.30, 0.60),
    ("returns-v1", "null_rate", "returns", "reason", 0.08, 0.15),
    ("fulfillment-v1", "freshness_hours", "fulfillment", None, 4.0, 8.0),
    ("analytics-v1", "row_count_delta", "customer_analytics", None, 0.15, 0.35),
]

CHECK_TYPES = ["field_is_present", "field_type", "field_required", "field_unique", "general"]


def now_minus(days=0, hours=0, minutes=0):
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)


def seed_contracts(api_url: str):
    print("Seeding contracts...")
    for c in CONTRACTS:
        resp = httpx.post(
            f"{api_url}/api/v1/contracts",
            json={
                "contract_id": c["contract_id"],
                "title": c["title"],
                "description": c["description"],
                "file_path": f"contracts/{c['contract_id']}.yaml",
                "owner_team": c["owner_team"],
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

            cur.execute(
                """INSERT INTO validation_runs
                   (id, contract_id, status, enforcement_mode,
                    checks_total, checks_passed, checks_failed,
                    failures, server, triggered_by, duration_ms, error_message, run_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    run_id, contract_id, status,
                    next(c["enforcement_mode"] for c in CONTRACTS if c["contract_id"] == contract_id),
                    checks_total, checks_passed, checks_failed,
                    psycopg2.extras.Json(failures) if failures else None,
                    None,
                    random.choice(["api", "scheduler", "ci"]),
                    duration_ms, error_message, run_at,
                ),
            )
    conn.commit()
    print(f"  + {sum(p['num_runs'] for p in RUN_PROFILES.values())} runs")


def seed_drift(conn):
    print("Seeding drift metrics and baselines...")
    cur = conn.cursor()
    for contract_id, metric_type, table_name, column_name, warn_t, breach_t in DRIFT_SPECS:
        for day in range(14):
            metric_id = str(uuid.uuid4())
            measured_at = now_minus(days=14 - day, hours=random.randint(0, 6))
            if "null_rate" in metric_type:
                base = warn_t * 0.3
                drift_factor = 1 + (day / 14) * 1.8
                value = round(base * drift_factor + random.uniform(-0.003, 0.003), 4)
            elif "row_count" in metric_type:
                base = warn_t * 0.4
                drift_factor = 1 + (day / 14) * 1.5
                value = round(base * drift_factor + random.uniform(-0.02, 0.02), 4)
            else:
                base = warn_t * 0.5
                drift_factor = 1 + (day / 14) * 1.2
                value = round(base * drift_factor + random.uniform(-0.5, 0.5), 2)

            is_warning = value >= warn_t and value < breach_t
            is_breached = value >= breach_t

            cur.execute(
                """INSERT INTO drift_metrics
                   (id, contract_id, run_id, metric_type, table_name, column_name,
                    value, warning_threshold, breach_threshold, is_warning, is_breached, measured_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    metric_id, contract_id, None, metric_type, table_name, column_name,
                    value, warn_t, breach_t, is_warning, is_breached, measured_at,
                ),
            )

        values = []
        for d in range(14):
            if "null_rate" in metric_type:
                values.append(warn_t * 0.3 * (1 + d / 14 * 1.8))
            elif "row_count" in metric_type:
                values.append(warn_t * 0.4 * (1 + d / 14 * 1.5))
            else:
                values.append(warn_t * 0.5 * (1 + d / 14 * 1.2))

        mean_val = sum(values) / len(values)
        std_val = (sum((v - mean_val) ** 2 for v in values) / len(values)) ** 0.5
        slope = (values[-1] - values[0]) / len(values)
        trending = slope > 0 and values[-1] > warn_t * 0.6
        est_breach = max(1, int((breach_t - values[-1]) / max(slope, 0.0001))) if trending else None

        cur.execute(
            """INSERT INTO drift_baselines
               (id, contract_id, metric_type, table_name, column_name,
                mean, std_dev, trend_slope, is_trending_to_breach,
                estimated_breach_in_runs, window_size, computed_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (contract_id, metric_type, table_name, column_name)
               DO UPDATE SET mean=EXCLUDED.mean, std_dev=EXCLUDED.std_dev,
                  trend_slope=EXCLUDED.trend_slope,
                  is_trending_to_breach=EXCLUDED.is_trending_to_breach,
                  estimated_breach_in_runs=EXCLUDED.estimated_breach_in_runs,
                  computed_at=EXCLUDED.computed_at""",
            (
                str(uuid.uuid4()), contract_id, metric_type, table_name, column_name,
                round(mean_val, 6), round(std_val, 6), round(slope, 6), trending,
                est_breach, 14, now_minus(hours=1),
            ),
        )

    conn.commit()
    print(f"  + {len(DRIFT_SPECS) * 14} drift metrics, {len(DRIFT_SPECS)} baselines")


def seed_teams_and_compliance(conn):
    print("Seeding teams and compliance scores...")
    cur = conn.cursor()
    team_ids = {}

    for name in TEAM_NAMES:
        tid = str(uuid.uuid4())
        team_ids[name] = tid
        cur.execute(
            """INSERT INTO teams (id, name, slack_channel, email, created_at)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (name) DO UPDATE SET id=teams.id RETURNING id""",
            (tid, name, f"#dc-{name.replace('team-', '')}", f"{name}@company.com", now_minus(days=90)),
        )
        row = cur.fetchone()
        if row:
            team_ids[name] = str(row[0])

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
    print(f"  + {len(TEAM_NAMES)} teams, {len(TEAM_NAMES) * 6} compliance periods")


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
        seed_runs(conn)
        seed_drift(conn)
        seed_teams_and_compliance(conn)
    finally:
        conn.close()

    print("\nDone! Open http://localhost:5173 to see the dashboard.")


if __name__ == "__main__":
    main()
