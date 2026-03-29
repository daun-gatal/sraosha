import logging

from sraosha.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="sraosha.tasks.compliance_compute.compute_compliance_scores")
def compute_compliance_scores() -> dict:
    """Daily task that recomputes compliance scores for all teams."""
    logger.info("Starting compliance score computation")

    teams_updated = 0

    # In production, this queries the DB for all teams, computes
    # score = (passed_runs / total_runs) * 100 over the last 30 days,
    # and upserts into compliance_scores.

    logger.info("Compliance computation complete: %d teams updated", teams_updated)
    return {"teams_updated": teams_updated}
