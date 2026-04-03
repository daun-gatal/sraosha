from __future__ import annotations

import json
import logging
import traceback
import uuid
from datetime import datetime, timezone

from psycopg2.extras import Json

from sraosha.crypto import decrypt
from sraosha.dq.runner import SodaCheckRunner
from sraosha.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _connection_row_to_params(row: tuple) -> tuple[dict, str]:
    (
        host,
        port,
        database,
        schema_name,
        account,
        warehouse,
        role,
        catalog,
        http_path,
        project,
        dataset,
        path,
        location,
        username,
        password_encrypted,
        token_encrypted,
        service_account_json_encrypted,
        extra_params_json,
        server_type,
    ) = row
    params: dict = {
        "host": host,
        "port": port,
        "database": database,
        "schema": schema_name,
        "username": username,
        "account": account,
        "warehouse": warehouse,
        "role": role,
        "catalog": catalog,
        "httpPath": http_path,
        "project": project,
        "dataset": dataset,
        "path": path,
        "location": location,
    }
    if password_encrypted:
        params["password"] = decrypt(password_encrypted)
    if token_encrypted:
        params["token"] = decrypt(token_encrypted)
    if service_account_json_encrypted:
        params["service_account_json"] = decrypt(service_account_json_encrypted)
    if extra_params_json and isinstance(extra_params_json, dict):
        params.update(extra_params_json)
    out = {k: v for k, v in params.items() if v is not None}
    return out, server_type


@celery_app.task(name="sraosha.tasks.dq_scan.run_dq_check")
def run_dq_check(dq_check_id: str, triggered_by: str = "manual") -> dict:
    from sraosha.tasks.db import get_sync_connection

    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    check_uuid = uuid.UUID(dq_check_id)
    logger.info("dq_scan start check_id=%s triggered_by=%s", dq_check_id, triggered_by)

    with get_sync_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """SELECT id, connection_id, data_source_name, sodacl_yaml
               FROM dq_checks WHERE id = %s""",
            (check_uuid,),
        )
        dq_row = cur.fetchone()
        if not dq_row:
            logger.warning("DQ check not found: %s", dq_check_id)
            return {"check_id": dq_check_id, "status": "skipped"}

        _dq_id, connection_id, data_source_name, sodacl_yaml = dq_row

        cur.execute(
            """SELECT host, port, database, schema_name, account, warehouse, role, catalog,
                      http_path, project, dataset, path, location, username,
                      password_encrypted, token_encrypted, service_account_json_encrypted,
                      extra_params, server_type
               FROM connections WHERE id = %s""",
            (connection_id,),
        )
        conn_row = cur.fetchone()
        if not conn_row:
            logger.warning("Connection not found for DQ check %s", dq_check_id)
            cur.execute(
                """INSERT INTO dq_check_runs
                   (id, dq_check_id, status, checks_total, checks_passed,
                    checks_warned, checks_failed, results_json, diagnostics_json,
                    run_log, duration_ms, triggered_by, run_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id,
                    check_uuid,
                    "error",
                    0,
                    0,
                    0,
                    0,
                    None,
                    Json(json.loads(json.dumps({"error": "connection_not_found"}))),
                    None,
                    None,
                    triggered_by,
                    now,
                ),
            )
            cur.execute(
                """UPDATE dq_schedules
                   SET last_run_at = %s, updated_at = %s
                   WHERE dq_check_id = %s""",
                (now, now, check_uuid),
            )
            return {"check_id": dq_check_id, "status": "error"}

        conn_params, server_type = _connection_row_to_params(conn_row)

        try:
            runner = SodaCheckRunner()
            out = runner.run(data_source_name, server_type, conn_params, sodacl_yaml)
            results_json = json.loads(json.dumps(out.results, default=str))
            diagnostics_json = json.loads(json.dumps(out.diagnostics, default=str))
            duration_ms = int(out.duration_seconds * 1000)
            cur.execute(
                """INSERT INTO dq_check_runs
                   (id, dq_check_id, status, checks_total, checks_passed,
                    checks_warned, checks_failed, results_json, diagnostics_json,
                    run_log, duration_ms, triggered_by, run_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id,
                    check_uuid,
                    out.status,
                    out.checks_total,
                    out.checks_passed,
                    out.checks_warned,
                    out.checks_failed,
                    Json(results_json),
                    Json(diagnostics_json),
                    out.log,
                    duration_ms,
                    triggered_by,
                    now,
                ),
            )
            cur.execute(
                """UPDATE dq_schedules
                   SET last_run_at = %s, updated_at = %s
                   WHERE dq_check_id = %s""",
                (now, now, check_uuid),
            )
            logger.info(
                "dq_scan done check_id=%s status=%s checks_total=%s",
                dq_check_id,
                out.status,
                out.checks_total,
            )
            return {"check_id": dq_check_id, "status": out.status}

        except Exception:
            logger.exception("DQ check run failed: %s", dq_check_id)
            err_tb = traceback.format_exc()
            cur.execute(
                """INSERT INTO dq_check_runs
                   (id, dq_check_id, status, checks_total, checks_passed,
                    checks_warned, checks_failed, results_json, diagnostics_json,
                    run_log, duration_ms, triggered_by, run_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id,
                    check_uuid,
                    "error",
                    0,
                    0,
                    0,
                    0,
                    None,
                    Json(
                        json.loads(
                            json.dumps({"error": "exception", "detail": err_tb}, default=str)
                        )
                    ),
                    err_tb,
                    None,
                    triggered_by,
                    now,
                ),
            )
            cur.execute(
                """UPDATE dq_schedules
                   SET last_run_at = %s, updated_at = %s
                   WHERE dq_check_id = %s""",
                (now, now, check_uuid),
            )
            return {"check_id": dq_check_id, "status": "error"}
