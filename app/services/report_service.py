from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.report import Report, ReportStatus
from app.schemas.report import ReportCreate


def create_report(db: Session, report_data: ReportCreate) -> Report:
    report = Report(
        report_type=report_data.report_type.value,
        status=ReportStatus.PENDING.value,
        start_date=report_data.start_date,
        end_date=report_data.end_date,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report_by_id(db: Session, report_id: str) -> Report | None:
    return db.get(Report, report_id)


def update_report_status(db: Session, report_id: str, status: str, error_message: str | None = None) -> Report | None:
    report = db.get(Report, report_id)
    if not report:
        return None

    report.status = status
    if status == ReportStatus.PROCESSING.value:
        report.started_at = datetime.now(timezone.utc)
    elif status in (ReportStatus.COMPLETED.value, ReportStatus.FAILED.value):
        report.completed_at = datetime.now(timezone.utc)

    if error_message is not None:
        report.error_message = error_message
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def set_report_file_path(db: Session, report_id: str, file_path: str) -> Report | None:
    report = db.get(Report, report_id)
    if not report:
        return None

    report.file_path = file_path
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_order_summary_metrics(db: Session, start_date, end_date):
    """
    Execute SQL-level aggregation for the order summary metrics.

    All calculations (COUNT, SUM, AVG, COUNT DISTINCT) are pushed down to
    PostgreSQL — no Python-side iteration over order rows.
    """
    from app.db.models.order import Order

    stmt = (
        select(
            func.count(Order.id).label("order_count"),
            func.sum(Order.total_amount).label("total_amount"),
            func.avg(Order.total_amount).label("average_order_value"),
            func.count(func.distinct(Order.customer_name)).label("unique_customers"),
        )
        .where(Order.order_date >= start_date)
        .where(Order.order_date <= end_date)
    )

    return db.execute(stmt).mappings().one()


def get_order_summary_by_customer(db: Session, start_date, end_date):
    """
    Execute a SQL GROUP BY aggregation to summarise orders per customer.

    Results are ordered by total revenue (DESC) entirely in SQL.
    """
    from app.db.models.order import Order

    stmt = (
        select(
            Order.customer_name,
            func.count(Order.id).label("order_count"),
            func.sum(Order.total_amount).label("total_amount"),
        )
        .where(Order.order_date >= start_date)
        .where(Order.order_date <= end_date)
        .group_by(Order.customer_name)
        .order_by(func.sum(Order.total_amount).desc())
    )

    return db.execute(stmt).mappings().all()
