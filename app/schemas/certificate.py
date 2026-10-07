"""
Certificate Pydantic Schemas.

Defines schemas for returning certificate information and status.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CertificateResponse(BaseModel):
    """
    Schema representing an individual certificate record.
    Used in GET /api/jobs/{job_id}/certificates and certificate status inspection.
    """
    id: int
    job_id: int
    recipient_name: str
    recipient_email: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
