"""
Job Service.

Contains domain and persistence logic for managing certificate generation jobs.
Keeps route handlers lean and focused purely on HTTP concerns.
"""
from sqlalchemy.orm import Session

from app.models.certificate import Certificate, CertificateStatus
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate


def create_bulk_job(db: Session, job_data: JobCreate) -> Job:
    """
    Creates a new Job along with pending Certificate records for all recipients.
    
    Performs batch insertion and establishes 1-to-many relationship.
    """
    new_job = Job(
        event_name=job_data.event_name,
        event_date=job_data.event_date,
        status=JobStatus.QUEUED.value,
        total_count=len(job_data.recipients),
        success_count=0,
        failure_count=0,
        border_style=job_data.border_style.value,
        border_color=job_data.border_color,
        border_width=job_data.border_width,
    )

    # Attach all recipient certificate records
    for recipient in job_data.recipients:
        cert = Certificate(
            recipient_name=recipient.name,
            recipient_email=str(recipient.email),
            status=CertificateStatus.PENDING.value,
        )
        new_job.certificates.append(cert)

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return new_job


def get_job_by_id(db: Session, job_id: int) -> Job | None:
    """
    Retrieves a Job by primary key, or None if not found.
    """
    return db.query(Job).filter(Job.id == job_id).first()


def get_job_certificates(db: Session, job_id: int) -> list[Certificate] | None:
    """
    Retrieves all Certificate records belonging to a Job, ordered by ID.
    Returns None if the Job does not exist.
    """
    job = get_job_by_id(db, job_id)
    if not job:
        return None
    return (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.id.asc())
        .all()
    )
