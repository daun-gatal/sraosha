"""Celery tasks for scheduled contract validation.

check_validation_schedules  -- runs every 60s via Beat, finds due schedules,
                               dispatches individual validation tasks.
run_contract_validation     -- validates a single contract and persists the result.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sraosha.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

PRESET_SECONDS: dict[str, int] = {
    "hourly": 3600,
    "every_6h": 21600,
    "every_12h": 43200,
    "daily": 86400,
    "weekly": 604800,
}


def _compute_next_run(preset: str, cron_expr: str | None, from_dt: datetime) -> datetime:
    if preset == "custom" and cron_expr:
        from croniter import croniter

        cron = croniter(cron_expr, from_dt)
        next_run = cast(datetime, cron.get_next(datetime))
        return next_run.replace(tzinfo=timezone.utc)

    seconds = PRESET_SECONDS.get(preset, 86400)
    return from_dt + timedelta(seconds=seconds)


@celery_app.task(name="sraosha.tasks.validation_scheduler.check_validation_schedules")
def check_validation_schedules() -> dict:
    """Find due schedules and dispatch validation tasks."""
    from sraosha.tasks.db import get_sync_connection

    now = datetime.now(timezone.utc)
    dispatched = 0

    with get_sync_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT contract_id, interval_preset, cron_expression
               FROM validation_schedules
               WHERE is_enabled = true AND next_run_at <= %s""",
            (now,),
        )
        due = cur.fetchall()

        for contract_id, preset, cron_expr in due:
            run_contract_validation.delay(contract_id)

            next_run = _compute_next_run(preset, cron_expr, now)
            cur.execute(
                """UPDATE validation_schedules
                   SET next_run_at = %s, updated_at = %s
                   WHERE contract_id = %s""",
                (next_run, now, contract_id),
            )
            dispatched += 1

    logger.info("Schedule check: %d contract(s) dispatched for validation", dispatched)
    return {"dispatched": dispatched}


def _resolve_scheduler_creds(cur, raw_yaml: str) -> tuple:
    """Resolve connection credentials for a contract's server block (sync cursor)."""
    import yaml as _yaml

    from sraosha.core.credentials import ordered_connection_names_from_contract_doc

    try:
        doc = _yaml.safe_load(raw_yaml) or {}
        servers = doc.get("servers", {})
        if not servers:
            return None, {}

        cols = (
            "server_type, username, password_encrypted, token_encrypted, "
            "service_account_json_encrypted"
        )

        for nm in ordered_connection_names_from_contract_doc(doc):
            cur.execute(f"SELECT {cols} FROM connections WHERE name = %s", (nm,))
            crow = cur.fetchone()
            if crow:
                return _parse_cred_row(crow)

        first_server: Any = next(iter(servers.values()), {})
        first_type: str = first_server.get("type", "") if isinstance(first_server, dict) else ""
        if first_type:
            cur.execute(
                f"SELECT {cols} FROM connections WHERE server_type = %s LIMIT 1",
                (first_type,),
            )
            crow = cur.fetchone()
            if crow:
                return _parse_cred_row(crow)
    except Exception:
        logger.debug("Could not resolve connection credentials", exc_info=True)

    return None, {}


def _parse_cred_row(row) -> tuple:
    from sraosha.crypto import decrypt

    server_type, username, pw_enc, tok_enc, sa_enc = row
    creds = {}
    if username:
        creds["username"] = username
    if pw_enc:
        creds["password"] = decrypt(pw_enc)
    if tok_enc:
        creds["token"] = decrypt(tok_enc)
    if sa_enc:
        creds["service_account_json"] = decrypt(sa_enc)
    return server_type, creds


@celery_app.task(
    name="sraosha.tasks.validation_scheduler.run_contract_validation",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def run_contract_validation(self, contract_id: str) -> dict:
    """Run validation for a single contract and persist the result."""
    from sraosha.tasks.db import get_sync_connection

    now = datetime.now(timezone.utc)

    with get_sync_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT raw_yaml, enforcement_mode FROM contracts WHERE contract_id = %s",
            (contract_id,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning("Schedule triggered for unknown contract %s", contract_id)
            return {"contract_id": contract_id, "status": "skipped", "reason": "not_found"}

        raw_yaml, enforcement_mode = row

        status = "error"
        checks_total = checks_passed = checks_failed = 0
        failures = None
        duration_ms = None
        error_message = None
        run_log = None

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
                tmp.write(raw_yaml)
                tmp_path = tmp.name

            from sraosha.core.credentials import inject_credentials
            from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode

            cred_type, creds = _resolve_scheduler_creds(cur, raw_yaml)

            engine = ContractEngine(
                contract_path=tmp_path,
                enforcement_mode=EnforcementMode(enforcement_mode),
                dry_run=True,
            )
            with inject_credentials(cred_type or "", creds):
                result = engine.run()

            status = "passed" if result.passed else "failed"
            checks_total = result.checks_total
            checks_passed = result.checks_passed
            checks_failed = result.checks_failed
            failures = result.failures or None
            duration_ms = int(result.duration_seconds * 1000)
            run_log = result.log or None

        except ContractViolationError as exc:
            status = "failed"
            checks_total = exc.result.checks_total
            checks_passed = exc.result.checks_passed
            checks_failed = exc.result.checks_failed
            failures = exc.result.failures or None
            duration_ms = int(exc.result.duration_seconds * 1000)
            run_log = exc.result.log or None

        except Exception as exc:
            error_message = str(exc)
            logger.exception("Scheduled validation error for %s", contract_id)

        import json

        cur.execute(
            """INSERT INTO validation_runs
               (id, contract_id, status, enforcement_mode,
                checks_total, checks_passed, checks_failed,
                failures, server, triggered_by, duration_ms, error_message, run_log, run_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                uuid.uuid4(),
                contract_id,
                status,
                enforcement_mode,
                checks_total,
                checks_passed,
                checks_failed,
                json.dumps(failures) if failures else None,
                "production",
                "scheduler",
                duration_ms,
                error_message,
                run_log,
                now,
            ),
        )

        cur.execute(
            """UPDATE validation_schedules
               SET last_run_at = %s, updated_at = %s
               WHERE contract_id = %s""",
            (now, now, contract_id),
        )

    logger.info("Scheduled validation for %s: %s", contract_id, status)
    return {"contract_id": contract_id, "status": status}
