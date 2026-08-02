"""
Celery Beat scheduled tasks.

These tasks are triggered automatically on a schedule (defined in celery_app.py).
They must never contain PDF generation logic directly — instead they determine
the reporting window, create the Report record, and dispatch the existing
generate_report_task pipeline via .delay().

Flow:
    Celery Beat
        ↓  (schedule fires)
    generate_daily_report()
        ↓  determine yesterday's date range
        ↓  create Report row (PENDING)
        ↓  generate_report_task.delay(report.id)
        ↓
      Redis
        ↓
    Celery Worker
        ↓
    Existing pipeline (SQL → ReportLab → storage → status update)
"""
from datetime import date, timedelta

from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.schemas.report import ReportCreate, ReportType
from app.services.report_service import create_report
from app.workers.report_tasks import generate_report_task

logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.scheduled_tasks.generate_daily_report")
def generate_daily_report() -> dict:
    """
    Auto-generate an order summary report for the previous calendar day.

    Scheduled via Celery Beat (see celery_app.conf.beat_schedule).
    Dispatches to generate_report_task so the actual PDF generation remains
    a background job — this task only orchestrates, it does not build the PDF.
    """
    yesterday = date.today() - timedelta(days=1)
    logger.info("Scheduling daily order summary report for %s", yesterday)

    db = SessionLocal()
    try:
        report_data = ReportCreate(
            report_type=ReportType.ORDER_SUMMARY,
            start_date=yesterday,
            end_date=yesterday,
        )
        report = create_report(db, report_data)
        logger.info("Created report record %s for date %s", report.id, yesterday)

        # Dispatch to the shared generation pipeline via Celery.
        # .delay() ensures PDF building happens in a worker, not in Beat.
        generate_report_task.delay(report.id)
        logger.info("Dispatched generate_report_task for report_id=%s", report.id)

        return {"report_id": report.id, "date": str(yesterday), "status": "dispatched"}
    finally:
        db.close()
