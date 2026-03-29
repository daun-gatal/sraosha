from celery import Celery

from sraosha.config import settings

celery_app = Celery(
    "sraosha",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "drift-scan-periodic": {
            "task": "sraosha.tasks.drift_scan.run_drift_scan",
            "schedule": settings.DRIFT_SCAN_INTERVAL_SECONDS,
        },
        "compliance-compute-daily": {
            "task": "sraosha.tasks.compliance_compute.compute_compliance_scores",
            "schedule": 86400,
        },
    },
)
