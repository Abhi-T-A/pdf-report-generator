"""
API-level tests for the /api/v1/reports endpoints.

Uses SQLite in-memory DB via the `client` and `test_db` fixtures from conftest.py.
The Celery task's `.delay()` is monkeypatched so no broker or worker is required.
"""
import importlib
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.db.models.order import Order

# Import the reports route module explicitly to avoid the naming ambiguity with
# app.api.routes.__init__ which re-exports `router as reports` (an APIRouter).
# Importing the module directly gives us access to the `generate_report_task` name.
_routes_module = importlib.import_module("app.api.routes.reports")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seed_orders(db: Session) -> None:
    orders = [
        Order(order_date=date(2026, 7, 1), customer_name="Acme Corp", total_amount=1200.50, status="completed"),
        Order(order_date=date(2026, 7, 2), customer_name="Beta LLC", total_amount=750.00, status="completed"),
        Order(order_date=date(2026, 7, 2), customer_name="Acme Corp", total_amount=240.00, status="completed"),
    ]
    db.add_all(orders)
    db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_report_invalid_date_range(client):
    """end_date before start_date must return 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/reports",
        json={
            "report_type": "order_summary",
            "start_date": "2026-07-10",
            "end_date": "2026-07-01",
        },
    )
    assert response.status_code == 422


def test_create_report_same_start_and_end_date(client, monkeypatch):
    """start_date == end_date is a valid single-day report window."""
    monkeypatch.setattr(_routes_module.generate_report_task, "delay", lambda *a, **kw: None)

    response = client.post(
        "/api/v1/reports",
        json={
            "report_type": "order_summary",
            "start_date": "2026-07-01",
            "end_date": "2026-07-01",
        },
    )
    assert response.status_code == 202


def test_create_report_and_get_status(client, test_db, monkeypatch):
    """
    POST creates a PENDING report and dispatches the task;
    GET returns the same report with a valid status.
    """
    monkeypatch.setattr(_routes_module.generate_report_task, "delay", lambda *a, **kw: None)

    seed_orders(test_db)

    response = client.post(
        "/api/v1/reports",
        json={
            "report_type": "order_summary",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["report_type"] == "order_summary"
    assert data["id"] is not None

    report_id = data["id"]
    fetch_resp = client.get(f"/api/v1/reports/{report_id}")
    assert fetch_resp.status_code == 200
    fetch_data = fetch_resp.json()
    assert fetch_data["id"] == report_id
    assert fetch_data["status"] in {"PENDING", "PROCESSING", "COMPLETED", "FAILED"}


def test_get_unknown_report(client):
    """Non-existent report_id must return 404."""
    response = client.get("/api/v1/reports/non-existent-id")
    assert response.status_code == 404


def test_download_not_ready_report(client, monkeypatch):
    """Downloading a PENDING report must return 400 Bad Request."""
    monkeypatch.setattr(_routes_module.generate_report_task, "delay", lambda *a, **kw: None)

    create_resp = client.post(
        "/api/v1/reports",
        json={
            "report_type": "order_summary",
            "start_date": "2026-07-01",
            "end_date": "2026-07-02",
        },
    )
    report_id = create_resp.json()["id"]

    download_resp = client.get(f"/api/v1/reports/{report_id}/download")
    assert download_resp.status_code == 400
