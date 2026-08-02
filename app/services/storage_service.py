from pathlib import Path

from app.core.config import settings


def ensure_storage_directory() -> Path:
    path = Path(settings.STORAGE_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_report_file_path(report_id: str) -> Path:
    storage_dir = ensure_storage_directory()
    return storage_dir / f"{report_id}.pdf"
