from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy.exc import OperationalError

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.database import SessionLocal
from app.services.pdf_service import ReportContent, build_pdf
from app.services.report_service import (
    get_order_summary_by_customer,
    get_order_summary_metrics,
    set_report_file_path,
    update_report_status,
)
from app.services.storage_service import get_report_file_path

logger = get_task_logger(__name__)

# Errors that are transient and worth retrying (e.g. brief DB blip, I/O error).
# All other exceptions are treated as non-retryable and go straight to FAILED.
TRANSIENT_EXCEPTIONS = (OperationalError, IOError, OSError)


@celery_app.task(
    bind=True,
    name="app.workers.report_tasks.generate_report_task",
    max_retries=3,
)
def generate_report_task(self, report_id: str) -> dict:
    """
    Generate a PDF order-summary report for the given report_id.

    State machine:
        PENDING → PROCESSING → COMPLETED
                             → FAILED  (non-retryable error, or max retries exceeded)
                             → PROCESSING (retry attempt) → ... → COMPLETED / FAILED

    Retry behaviour:
        - Transient errors (DB blips, I/O): exponential backoff, up to max_retries.
        - Non-retryable errors: mark FAILED immediately, re-raise for Celery consistency.
    """
    db = SessionLocal()
    try:
        report = update_report_status(db, report_id, "PROCESSING")
        if not report:
            raise ValueError(f"Report {report_id} not found in database")

        summary = get_order_summary_metrics(db, report.start_date, report.end_date)
        customer_rows = get_order_summary_by_customer(db, report.start_date, report.end_date)

        file_path = get_report_file_path(report.id)
        content = ReportContent(
            report_title="Order Summary Report",
            start_date=report.start_date.isoformat(),
            end_date=report.end_date.isoformat(),
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary={
                "order_count": summary["order_count"] or 0,
                "total_amount": float(summary["total_amount"] or 0.0),
                "average_order_value": float(summary["average_order_value"] or 0.0),
                "unique_customers": summary["unique_customers"] or 0,
            },
            customer_rows=customer_rows,
        )
        build_pdf(file_path, content)
        set_report_file_path(db, report.id, str(file_path))
        update_report_status(db, report.id, "COMPLETED")

        return {"status": "COMPLETED", "report_id": report.id, "file_path": str(file_path)}

    except TRANSIENT_EXCEPTIONS as exc:
        attempt = self.request.retries + 1
        logger.warning(
            "Transient error for report %s (attempt %d/%d): %s",
            report_id, attempt, self.max_retries + 1, exc,
        )
        if self.request.retries >= self.max_retries:
            # Max retries exhausted — mark the report as permanently failed.
            logger.error("Max retries exhausted for report %s", report_id)
            update_report_status(db, report_id, "FAILED", error_message=str(exc))
            raise  # re-raise so Celery task state also shows FAILURE

        # Exponential backoff: 10s, 20s, 40s
        countdown = 10 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception as exc:
        # Non-retryable error — fail immediately.
        logger.exception("Non-retryable error for report %s", report_id)
        update_report_status(db, report_id, "FAILED", error_message=str(exc))
        raise  # re-raise so Celery task state is consistent with FAILED report status

    finally:
        db.close()
