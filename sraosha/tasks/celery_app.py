from celery import Celery

from sraosha.config import settings

celery_app = Celery(
    "sraosha",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "sraosha.tasks.validation_scheduler",
        "sraosha.tasks.dq_scan",
        "sraosha.tasks.dq_scheduler",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-validation-schedules": {
            "task": "sraosha.tasks.validation_scheduler.check_validation_schedules",
            "schedule": 60,
        },
        "check-dq-schedules": {
            "task": "sraosha.tasks.dq_scheduler.check_dq_schedules",
            "schedule": 60,
        },
    },
)
