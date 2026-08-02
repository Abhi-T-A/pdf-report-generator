from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "pdf_report_generator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Routing: dedicated queue for report generation
celery_app.conf.task_routes = {
    "app.workers.report_tasks.generate_report_task": {"queue": "reports"},
    "app.workers.scheduled_tasks.generate_daily_report": {"queue": "reports"},
}

celery_app.conf.enable_utc = True
celery_app.conf.timezone = "UTC"
celery_app.conf.task_always_eager = settings.CELERY_TASK_ALWAYS_EAGER

# ---------------------------------------------------------------------------
# Celery Beat schedule (stretch goal)
# ---------------------------------------------------------------------------
# generate_daily_report fires at 01:00 UTC every day and dispatches
# generate_report_task for the previous calendar day's orders.
celery_app.conf.beat_schedule = {
    "daily-order-summary-report": {
        "task": "app.workers.scheduled_tasks.generate_daily_report",
        "schedule": crontab(hour=1, minute=0),  # 01:00 UTC daily
    },
}

# Auto-discover tasks in both workers modules.
# This ensures Beat and Worker both see all registered task names.
celery_app.autodiscover_tasks(
    [
        "app.workers.report_tasks",
        "app.workers.scheduled_tasks",
    ]
)
