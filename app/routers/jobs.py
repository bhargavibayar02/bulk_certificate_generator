"""
Jobs Router.

Exposes endpoints for creating and managing bulk certificate generation jobs,
supporting both raw JSON payloads and multipart/form-data for logo file uploads.
"""
import json
from datetime import date
from typing import List
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.border import BorderStyle
from app.schemas.certificate import CertificateResponse
from app.schemas.job import JobCreate, JobCreateResponse, JobProgressResponse
from app.services.job_service import (
    create_bulk_job,
    get_job_by_id,
    get_job_certificates,
)
from app.services.job_processor import process_bulk_job
from app.services.logo_processor import validate_and_save_logos

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job (JSON)",
    description=(
        "Submits a bulk certificate request with an event name, event date, "
        "border customization options, and recipient list as JSON. Creates the job and "
        "initiates asynchronous background processing."
    )
)
def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Accepts bulk certificate generation payload, saves Job and Certificate
    records, and enqueues background processing.
    """
    job = create_bulk_job(db, job_data)
    background_tasks.add_task(process_bulk_job, job.id)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count
    )


@router.post(
    "/upload",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create bulk certificate generation job with logos (multipart/form-data)",
    description=(
        "Submits a bulk certificate generation request accepting 0 to 10 logo files. "
        "Parameters: event_name, event_date (YYYY-MM-DD), recipients (JSON string), "
        "border_style, border_color, border_width, and logos (files)."
    )
)
async def create_job_with_logos(
    background_tasks: BackgroundTasks,
    event_name: str = Form(...),
    event_date: date = Form(...),
    recipients: str = Form(..., description="JSON array of recipient objects: [{'name': '...', 'email': '...'}]"),
    border_style: BorderStyle = Form(BorderStyle.DOUBLE),
    border_color: str = Form("#1E3A8A"),
    border_width: int = Form(2),
    logos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """
    Accepts multipart/form-data for bulk certificate generation with optional logos.
    """
    # 1. Parse and validate recipients JSON string
    try:
        raw_recipients = json.loads(recipients)
        if not isinstance(raw_recipients, list):
            raise ValueError("Recipients must be a JSON array of objects.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed recipients JSON string: {exc}"
        )

    # 2. Validate complete payload using JobCreate schema
    try:
        job_payload = JobCreate(
            event_name=event_name,
            event_date=event_date,
            border_style=border_style,
            border_color=border_color,
            border_width=border_width,
            recipients=raw_recipients,
        )
    except ValidationError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=val_err.errors()
        )

    # 3. Create Job and Certificate records in DB
    job = create_bulk_job(db, job_payload)

    # 4. Validate and persist uploaded logos (if any)
    logo_paths = validate_and_save_logos(job.id, logos)

    # 5. Dispatch background task with logo paths
    background_tasks.add_task(process_bulk_job, job.id, logo_paths)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count
    )


@router.get(
    "/{job_id}",
    response_model=JobProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job progress and status",
    description=(
        "Returns the real-time status and progress metrics of a bulk generation job, "
        "including total, success, failure, pending counts, and progress percentage."
    )
)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Returns real-time progress metrics for a given job ID.
    Raises HTTP 404 if the job does not exist.
    """
    job = get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    return JobProgressResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        success_count=job.success_count,
        failure_count=job.failure_count,
        pending_count=job.pending_count,
        progress_percentage=job.progress_percentage,
        event_name=job.event_name,
        event_date=job.event_date,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/{job_id}/certificates",
    response_model=List[CertificateResponse],
    status_code=status.HTTP_200_OK,
    summary="List certificates belonging to a job",
    description=(
        "Returns the list of certificate records belonging to a job, including "
        "recipient details, status, and error messages if any. "
        "Does NOT return PDF binary contents."
    )
)
def list_job_certificates(job_id: int, db: Session = Depends(get_db)):
    """
    Returns certificate records belonging to the job.
    Raises HTTP 404 if the job does not exist.
    """
    certificates = get_job_certificates(db, job_id)
    if certificates is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    return certificates
