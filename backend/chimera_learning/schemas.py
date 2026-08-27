from __future__ import annotations

from enum import StrEnum
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LearningReportType(StrEnum):
    OVERVIEW = "overview"
    ACTIONS = "actions"
    FAILURES = "failures"
    FUNNEL = "funnel"
    PROVIDERS = "providers"
    CALIBRATION = "calibration"
    DRIFT = "drift"
    INSIGHTS = "insights"
    RECOMMENDATIONS = "recommendations"


class LearningReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_type: LearningReportType
    provider_mode: str | None = Field(default=None, min_length=1, max_length=16)
    baseline_days: int = Field(default=30, ge=1, le=3650)
    current_days: int = Field(default=7, ge=1, le=3650)


class LearningReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    report_type: str
    analysis_version: str
    generated_at: datetime
    baseline_window: str | None
    current_window: str | None
    input_hash: str
    output_hash: str
    structured_report: dict
