"""
Job Pydantic Schemas.

Defines schemas and strong validation for bulk job creation,
job status tracking, and progress metrics.
"""
import re
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.schemas.border import BorderStyle, HEX_COLOR_REGEX
from app.schemas.recipient import RecipientCreate


class JobCreate(BaseModel):
    """
    Payload for creating a new bulk certificate generation job.
    """
    event_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the event or workshop, e.g. 'Cyber Security Workshop'."
    )
    event_date: date = Field(
        ...,
        description="Date when the event was held (YYYY-MM-DD)."
    )
    border_style: BorderStyle = Field(
        default=BorderStyle.DOUBLE,
        description="Controlled border style: 'none', 'single', 'double', or 'thick'."
    )
    border_color: str = Field(
        default="#1E3A8A",
        description="Hexadecimal color for the border (e.g., '#1E3A8A')."
    )
    border_width: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Border line width between 1 and 10 points."
    )
    recipients: List[RecipientCreate] = Field(
        ...,
        min_length=1,
        description="List of recipients to receive certificates. Must contain at least 1 recipient."
    )

    @field_validator("event_name", mode="before")
    @classmethod
    def validate_event_name(cls, value: str) -> str:
        """
        Trim whitespace and ensure event_name is not empty or whitespace-only.
        """
        if not isinstance(value, str):
            raise ValueError("Event name must be a string")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Event name cannot be empty or whitespace only")
        return trimmed

    @field_validator("border_color")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        """
        Validate hex color string.
        """
        trimmed = value.strip()
        if not HEX_COLOR_REGEX.match(trimmed):
            raise ValueError(
                f"Invalid hex color format: '{value}'. Expected format like #1E3A8A or #333."
            )
        return trimmed.upper()

    @field_validator("recipients")
    @classmethod
    def validate_recipients_limit(cls, value: List[RecipientCreate]) -> List[RecipientCreate]:
        """
        Enforce configurable upper bound on recipients to prevent system exhaustion.
        """
        if len(value) > settings.MAX_RECIPIENTS_PER_JOB:
            raise ValueError(
                f"Maximum allowed recipients per job is {settings.MAX_RECIPIENTS_PER_JOB}. "
                f"Received: {len(value)} recipients."
            )
        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_name": "Cyber Security Workshop",
                "event_date": "2026-10-15",
                "border_style": "double",
                "border_color": "#1E3A8A",
                "border_width": 2,
                "recipients": [
                    {
                        "name": "Bhargavi Bayar",
                        "email": "bhargavi@example.com"
                    },
                    {
                        "name": "Rahul Kumar",
                        "email": "rahul@example.com"
                    }
                ]
            }
        }
    }


class JobCreateResponse(BaseModel):
    """
    Immediate asynchronous acceptance response returned upon job creation (HTTP 202).
    """
    job_id: int
    status: str
    total_count: int

    model_config = ConfigDict(from_attributes=True)


class JobProgressResponse(BaseModel):
    """
    Detailed progress report for a job returned by GET /api/jobs/{job_id}.
    """
    job_id: int
    status: str
    total_count: int
    success_count: int
    failure_count: int
    pending_count: int
    progress_percentage: float
    event_name: Optional[str] = None
    event_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
