from __future__ import annotations

import logging
from datetime import datetime, timezone

from sraosha.tasks.celery_app import celery_app
from sraosha.tasks.validation_scheduler import _compute_next_run

logger = logging.getLogger(__name__)


@celery_app.task(name="sraosha.tasks.dq_scheduler.check_dq_schedules")
def check_dq_schedules() -> dict:
    from sraosha.tasks.db import get_sync_connection
    from sraosha.tasks.dq_scan import run_dq_check

    now = datetime.now(timezone.utc)
    dispatched = 0

    with get_sync_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, dq_check_id, interval_preset, cron_expression
               FROM dq_schedules
               WHERE is_enabled = true AND next_run_at <= %s""",
            (now,),
        )
        due = cur.fetchall()

        for sched_id, dq_check_id, preset, cron_expr in due:
            run_dq_check.delay(str(dq_check_id), "scheduler")
            next_run = _compute_next_run(preset, cron_expr, now)
            cur.execute(
                """UPDATE dq_schedules
                   SET next_run_at = %s, updated_at = %s
                   WHERE id = %s""",
                (next_run, now, sched_id),
            )
            dispatched += 1

    logger.info("DQ schedule check: %d task(s) dispatched", dispatched)
    return {"dispatched": dispatched}
