"""
Integration tests for report_service against a real PostgreSQL database.

These tests verify that SQL-level aggregation (COUNT, SUM, AVG, GROUP BY)
works correctly — this is a key learning objective of the workshop.

Prerequisites:
  - Set TEST_DATABASE_URL in .env
  - Run: pytest tests/integration/ -v
"""
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.order import Order
from app.db.models.report import ReportStatus
from app.schemas.report import ReportCreate, ReportType
from app.services.report_service import (
    create_report,
    get_order_summary_by_customer,
    get_order_summary_metrics,
    get_report_by_id,
    update_report_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tables(integration_db: Session):
    """Wipe test data after every test to ensure isolation."""
    yield
    integration_db.execute(text("DELETE FROM reports"))
    integration_db.execute(text("DELETE FROM orders"))
    integration_db.commit()


def seed_orders(db: Session) -> None:
    orders = [
        Order(order_date=date(2026, 7, 1), customer_name="Acme Corp", total_amount=1200.50, status="completed"),
        Order(order_date=date(2026, 7, 2), customer_name="Beta LLC", total_amount=750.00, status="completed"),
        Order(order_date=date(2026, 7, 2), customer_name="Acme Corp", total_amount=240.00, status="completed"),
        Order(order_date=date(2026, 7, 3), customer_name="Delta Inc", total_amount=1830.90, status="completed"),
        Order(order_date=date(2026, 7, 5), customer_name="Echo Co", total_amount=520.45, status="completed"),
    ]
    db.add_all(orders)
    db.commit()


# ---------------------------------------------------------------------------
# Report CRUD
# ---------------------------------------------------------------------------

class TestCreateReport:
    def test_creates_with_pending_status(self, integration_db: Session):
        data = ReportCreate(
            report_type=ReportType.ORDER_SUMMARY,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
        report = create_report(integration_db, data)

        assert report.id is not None
        assert report.status == ReportStatus.PENDING.value
        assert report.report_type == "order_summary"
        assert report.created_at is not None

    def test_get_report_by_id(self, integration_db: Session):
        data = ReportCreate(
            report_type=ReportType.ORDER_SUMMARY,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
        report = create_report(integration_db, data)
        fetched = get_report_by_id(integration_db, report.id)

        assert fetched is not None
        assert fetched.id == report.id

    def test_get_nonexistent_report_returns_none(self, integration_db: Session):
        assert get_report_by_id(integration_db, "does-not-exist") is None


class TestUpdateReportStatus:
    def test_processing_sets_started_at(self, integration_db: Session):
        report = create_report(
            integration_db,
            ReportCreate(
                report_type=ReportType.ORDER_SUMMARY,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
            ),
        )
        updated = update_report_status(integration_db, report.id, ReportStatus.PROCESSING.value)

        assert updated.status == ReportStatus.PROCESSING.value
        assert updated.started_at is not None
        assert updated.completed_at is None

    def test_completed_sets_completed_at(self, integration_db: Session):
        report = create_report(
            integration_db,
            ReportCreate(
                report_type=ReportType.ORDER_SUMMARY,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
            ),
        )
        update_report_status(integration_db, report.id, ReportStatus.PROCESSING.value)
        updated = update_report_status(integration_db, report.id, ReportStatus.COMPLETED.value)

        assert updated.status == ReportStatus.COMPLETED.value
        assert updated.completed_at is not None

    def test_failed_stores_error_message(self, integration_db: Session):
        report = create_report(
            integration_db,
            ReportCreate(
                report_type=ReportType.ORDER_SUMMARY,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
            ),
        )
        error_msg = "Database connection timed out"
        updated = update_report_status(
            integration_db, report.id, ReportStatus.FAILED.value, error_message=error_msg
        )

        assert updated.status == ReportStatus.FAILED.value
        assert updated.error_message == error_msg


# ---------------------------------------------------------------------------
# SQL Aggregation — this is the key learning objective
# ---------------------------------------------------------------------------

class TestSQLAggregation:
    """
    Verify that aggregation (COUNT, SUM, AVG, GROUP BY) is executed in SQL,
    not in Python. These tests query a real PostgreSQL instance to confirm
    correct dialect behavior.
    """

    def test_metrics_total_count_and_amount(self, integration_db: Session):
        seed_orders(integration_db)

        metrics = get_order_summary_metrics(
            integration_db,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

        assert metrics["order_count"] == 5
        assert abs(float(metrics["total_amount"]) - 4541.85) < 0.01
        assert metrics["unique_customers"] == 4

    def test_metrics_average_order_value(self, integration_db: Session):
        seed_orders(integration_db)

        metrics = get_order_summary_metrics(
            integration_db,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

        expected_avg = 4541.85 / 5
        assert abs(float(metrics["average_order_value"]) - expected_avg) < 0.01

    def test_metrics_filtered_by_date_range(self, integration_db: Session):
        seed_orders(integration_db)

        # Only July 1 orders
        metrics = get_order_summary_metrics(
            integration_db,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
        )
        assert metrics["order_count"] == 1
        assert abs(float(metrics["total_amount"]) - 1200.50) < 0.01

    def test_customer_summary_groups_by_customer(self, integration_db: Session):
        seed_orders(integration_db)

        rows = get_order_summary_by_customer(
            integration_db,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

        assert len(rows) == 4
        customer_names = {r["customer_name"] for r in rows}
        assert customer_names == {"Acme Corp", "Beta LLC", "Delta Inc", "Echo Co"}

    def test_customer_summary_ordered_by_revenue_desc(self, integration_db: Session):
        seed_orders(integration_db)

        rows = get_order_summary_by_customer(
            integration_db,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

        # Delta Inc has the highest total_amount (1830.90)
        assert rows[0]["customer_name"] == "Delta Inc"

    def test_customer_summary_acme_corp_aggregated(self, integration_db: Session):
        """Acme Corp has two orders — they should be aggregated into one row."""
        seed_orders(integration_db)

        rows = get_order_summary_by_customer(
            integration_db,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

        acme_rows = [r for r in rows if r["customer_name"] == "Acme Corp"]
        assert len(acme_rows) == 1  # GROUP BY must aggregate, not duplicate
        assert acme_rows[0]["order_count"] == 2
        assert abs(float(acme_rows[0]["total_amount"]) - 1440.50) < 0.01

    def test_empty_date_range_returns_zeros(self, integration_db: Session):
        """Date range with no orders should return zero counts, not an error."""
        seed_orders(integration_db)

        metrics = get_order_summary_metrics(
            integration_db,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
        assert (metrics["order_count"] or 0) == 0
