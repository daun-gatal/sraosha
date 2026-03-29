import logging

from sraosha.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="sraosha.tasks.drift_scan.run_drift_scan")
def run_drift_scan() -> dict:
    """Periodic task that scans all active contracts for drift metrics."""
    from sraosha.config import settings

    logger.info("Starting periodic drift scan (window=%d)", settings.DRIFT_BASELINE_WINDOW)

    scanned = 0
    alerts_raised = 0

    # In production, this queries the DB for all active contracts with drift_metrics configured,
    # runs the DriftScanner against each data source, and persists results.
    # Here we provide the structure; the actual DB queries are wired in when the API is available.

    logger.info(
        "Drift scan complete: %d contracts scanned, %d alerts raised",
        scanned,
        alerts_raised,
    )
    return {"scanned": scanned, "alerts_raised": alerts_raised}
