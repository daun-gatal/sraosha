import logging
import uuid

from sraosha.compliance.scoring import (
    compliance_score_percent,
    rolling_30d_window,
    violation_count,
)
from sraosha.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="sraosha.tasks.compliance_compute.compute_compliance_scores")
def compute_compliance_scores() -> dict:
    """Daily task: recompute rolling 30d compliance scores per team from validation runs."""
    from datetime import datetime, timezone

    from sraosha.tasks.db import get_sync_connection

    now = datetime.now(timezone.utc)
    cutoff, end, period_start, period_end = rolling_30d_window(now)
    teams_updated = 0

    with get_sync_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM teams ORDER BY name")
        teams = cur.fetchall()

        for (team_id,) in teams:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int,
                    COUNT(*) FILTER (WHERE vr.status = 'passed')::int,
                    COUNT(*) FILTER (WHERE vr.status = 'failed')::int,
                    COUNT(*) FILTER (WHERE vr.status = 'error')::int
                FROM validation_runs vr
                INNER JOIN contracts c ON c.contract_id = vr.contract_id
                WHERE c.team_id = %s
                  AND vr.run_at >= %s AND vr.run_at <= %s
                """,
                (team_id, cutoff, end),
            )
            row = cur.fetchone()
            if not row:
                continue
            total, passed, failed, err = row
            failed = failed or 0
            err = err or 0
            if total == 0:
                continue

            score = compliance_score_percent(passed, total)
            if score is None:
                continue
            viol = violation_count(failed, err)

            cur.execute(
                """
                INSERT INTO compliance_scores
                    (id, team_id, score, total_runs, passed_runs, violations_count,
                     period_start, period_end, computed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (team_id, period_start, period_end)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    total_runs = EXCLUDED.total_runs,
                    passed_runs = EXCLUDED.passed_runs,
                    violations_count = EXCLUDED.violations_count,
                    computed_at = EXCLUDED.computed_at
                """,
                (
                    str(uuid.uuid4()),
                    team_id,
                    float(score),
                    total,
                    passed,
                    viol,
                    period_start,
                    period_end,
                    now,
                ),
            )
            teams_updated += 1

    logger.info("Compliance computation complete: %d team(s) updated", teams_updated)
    return {"teams_updated": teams_updated}
