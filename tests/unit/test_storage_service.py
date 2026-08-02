"""
Unit tests for storage_service.

No real filesystem side-effects — uses pytest's tmp_path and unittest.mock.patch
to avoid touching the configured STORAGE_PATH.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.storage_service import ensure_storage_directory, get_report_file_path


class TestGetReportFilePath:
    def test_returns_pdf_extension(self, tmp_path: Path) -> None:
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.STORAGE_PATH = str(tmp_path)
            result = get_report_file_path("some-report-id")

        assert result.suffix == ".pdf"

    def test_filename_matches_report_id(self, tmp_path: Path) -> None:
        report_id = "abc-123-def"
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.STORAGE_PATH = str(tmp_path)
            result = get_report_file_path(report_id)

        assert result.name == f"{report_id}.pdf"

    def test_path_is_under_storage_dir(self, tmp_path: Path) -> None:
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.STORAGE_PATH = str(tmp_path)
            result = get_report_file_path("some-id")

        assert result.parent == tmp_path

    def test_different_ids_produce_different_paths(self, tmp_path: Path) -> None:
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.STORAGE_PATH = str(tmp_path)
            path_a = get_report_file_path("id-a")
            path_b = get_report_file_path("id-b")

        assert path_a != path_b


class TestEnsureStorageDirectory:
    def test_creates_directory_if_not_exists(self, tmp_path: Path) -> None:
        nested = tmp_path / "deeply" / "nested" / "reports"
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.STORAGE_PATH = str(nested)
            result = ensure_storage_directory()

        assert result.exists()
        assert result.is_dir()

    def test_is_idempotent(self, tmp_path: Path) -> None:
        """Calling twice should not raise even if the directory already exists."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.STORAGE_PATH = str(tmp_path / "reports")
            ensure_storage_directory()
            ensure_storage_directory()  # second call — must not raise
