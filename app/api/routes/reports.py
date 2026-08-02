from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.report_service import create_report as create_report_record
from app.services.report_service import get_report_by_id
from app.workers.report_tasks import generate_report_task
from app.schemas.report import ReportCreate, ReportRead

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("", response_model=ReportRead, status_code=status.HTTP_202_ACCEPTED)
def create_report(report_data: ReportCreate, db: Session = Depends(get_db)):
    report = create_report_record(db, report_data)
    generate_report_task.delay(report.id)
    return report


@router.get("/{report_id}", response_model=ReportRead)
def read_report(report_id: str, request: Request, db: Session = Depends(get_db)):
    report = get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    response = ReportRead.model_validate(report)
    if report.status == "COMPLETED" and report.file_path:
        try:
            download_url = request.url_for("download_report", report_id=report.id)
            response.download_url = str(download_url)
        except Exception:
            response.download_url = None
    return response


@router.get("/{report_id}/download", name="download_report")
def download_report(report_id: str, db: Session = Depends(get_db)):
    report = get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if report.status != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report is not ready for download")
    if not report.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file path is missing")

    file_path = Path(report.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found")

    return FileResponse(path=file_path, filename=file_path.name, media_type="application/pdf")
