from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportType(str, Enum):
    ORDER_SUMMARY = "order_summary"


class ReportCreate(BaseModel):
    report_type: ReportType = Field(..., description="Type of report to generate")
    start_date: date = Field(..., description="Report start date")
    end_date: date = Field(..., description="Report end date")

    @model_validator(mode="after")
    def validate_date_range(self) -> "ReportCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be the same as or later than start_date")
        return self


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_type: ReportType
    status: str
    start_date: date
    end_date: date
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
