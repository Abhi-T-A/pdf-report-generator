"""
Unit tests for pdf_service.build_pdf.

No database required — tests only the PDF generation layer.
"""
from pathlib import Path

import pytest

from app.services.pdf_service import ReportContent, build_pdf


def _make_content(**overrides) -> ReportContent:
    defaults = dict(
        report_title="Test Order Summary Report",
        start_date="2026-07-01",
        end_date="2026-07-31",
        generated_at="2026-08-01T00:00:00+00:00",
        summary={
            "order_count": 3,
            "total_amount": 2190.50,
            "average_order_value": 730.17,
            "unique_customers": 2,
        },
        customer_rows=[
            {"customer_name": "Acme Corp", "order_count": 2, "total_amount": 1440.50},
            {"customer_name": "Beta LLC", "order_count": 1, "total_amount": 750.00},
        ],
    )
    defaults.update(overrides)
    return ReportContent(**defaults)


class TestBuildPdf:
    def test_creates_file(self, tmp_path: Path) -> None:
        """build_pdf must write a non-empty file at the specified path."""
        output = tmp_path / "report.pdf"
        build_pdf(output, _make_content())

        assert output.exists()
        assert output.stat().st_size > 0

    def test_output_is_valid_pdf(self, tmp_path: Path) -> None:
        """The generated file must begin with the PDF magic bytes (%PDF)."""
        output = tmp_path / "report.pdf"
        build_pdf(output, _make_content())

        with open(output, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

    def test_empty_customer_rows(self, tmp_path: Path) -> None:
        """Zero customer rows should still produce a valid PDF without raising."""
        output = tmp_path / "empty.pdf"
        content = _make_content(
            customer_rows=[],
            summary={
                "order_count": 0,
                "total_amount": 0.0,
                "average_order_value": 0.0,
                "unique_customers": 0,
            },
        )
        build_pdf(output, content)

        assert output.exists()
        with open(output, "rb") as f:
            assert f.read(4) == b"%PDF"

    def test_large_customer_list(self, tmp_path: Path) -> None:
        """Build should handle many customer rows without error."""
        output = tmp_path / "large.pdf"
        rows = [
            {"customer_name": f"Customer {i}", "order_count": i, "total_amount": float(i * 100)}
            for i in range(1, 51)
        ]
        build_pdf(output, _make_content(customer_rows=rows))
        assert output.exists()
