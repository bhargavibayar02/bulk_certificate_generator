"""
Job Background Processor Service.

Coordinates asynchronous bulk certificate generation:
- Isolated database session management.
- Granular certificate status tracking (pending -> processing -> completed/failed).
- Strong failure isolation: single certificate failures never interrupt the remaining batch.
- Accurate aggregated final job status (completed, completed_with_errors, failed).
"""
import logging
from pathlib import Path
from typing import Callable, List, Optional
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import Job, JobStatus
from app.services.certificate_generator import (
    generate_certificate_pdf,
    get_safe_certificate_path,
)

logger = logging.getLogger(__name__)


def process_bulk_job(
    job_id: int,
    logo_paths: Optional[List[Path]] = None,
    session_factory: Optional[sessionmaker[Session]] = None,
) -> None:
    """
    Executes bulk certificate generation for the specified job.

    Designed with failure isolation: an exception encountered during one
    recipient's certificate generation is logged and saved in that certificate's
    error_message, while remaining certificates continue processing uninterrupted.
    
    Database Session Handling:
    Always opens a dedicated database session using SessionLocal() (or session_factory),
    ensuring it does not rely on any request-scoped session.
    """
    factory = session_factory or SessionLocal
    db: Session = factory()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[Job {job_id}] Not found for background processing.")
            return

        # 1. Transition Job to processing status
        job.status = JobStatus.PROCESSING.value
        db.commit()
        logger.info(f"[Job {job_id}] Status set to PROCESSING. Total certificates: {job.total_count}")

        # Check for any saved logos for this job if not explicitly passed
        if logo_paths is None:
            from app.services.logo_processor import get_job_logos
            logo_paths = get_job_logos(job_id)

        # 2. Process each certificate with failure isolation
        certificates: List[Certificate] = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id)
            .order_by(Certificate.id.asc())
            .all()
        )

        for cert in certificates:
            # Mark certificate as currently processing
            cert.status = CertificateStatus.PROCESSING.value
            db.commit()

            try:
                # Generate collision-free safe destination path
                output_file = get_safe_certificate_path(cert.id)

                # Render landscape A4 PDF via ReportLab
                generate_certificate_pdf(
                    recipient_name=cert.recipient_name,
                    event_name=job.event_name,
                    event_date=job.event_date,
                    cert_id=cert.id,
                    output_path=output_file,
                    border_style=job.border_style,
                    border_color=job.border_color,
                    border_width=job.border_width,
                    logo_paths=logo_paths,
                )

                # Record success
                cert.status = CertificateStatus.COMPLETED.value
                cert.file_path = str(output_file)
                cert.error_message = None
                job.success_count += 1
                logger.info(f"[Job {job_id}] Certificate {cert.id} for '{cert.recipient_name}' generated successfully.")

            except Exception as exc:
                # Isolate failure: Record error and continue loop
                logger.error(f"[Job {job_id}] Certificate {cert.id} for '{cert.recipient_name}' failed: {exc}")
                cert.status = CertificateStatus.FAILED.value
                cert.file_path = None
                cert.error_message = str(exc)
                job.failure_count += 1

            finally:
                # Commit progress immediately after each certificate
                db.commit()

        # 3. Compute final Job status
        if job.total_count == 0:
            job.status = JobStatus.COMPLETED.value
        elif job.success_count == job.total_count:
            job.status = JobStatus.COMPLETED.value
        elif job.failure_count == job.total_count:
            job.status = JobStatus.FAILED.value
        else:
            job.status = JobStatus.COMPLETED_WITH_ERRORS.value

        db.commit()
        logger.info(
            f"[Job {job_id}] Finished with status={job.status} "
            f"(Success: {job.success_count}, Failures: {job.failure_count}, Total: {job.total_count})"
        )

    except Exception as fatal_exc:
        logger.exception(f"[Job {job_id}] Fatal unhandled exception in background worker: {fatal_exc}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status not in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_ERRORS.value):
                job.status = JobStatus.FAILED.value
                db.commit()
        except Exception:
            pass

    finally:
        # Guarantee session is closed
        db.close()
