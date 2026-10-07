"""
Phase 7 Certificate Retrieval Tests.

Tests the GET /api/certificates/{certificate_id} endpoint:
1. Successfully downloads valid generated PDF certificate (HTTP 200, application/pdf).
2. Returns HTTP 404 when certificate ID does not exist.
3. Returns HTTP 400 with a descriptive error when certificate generation has failed.
4. Returns HTTP 409 when certificate generation is still pending or processing.
5. Returns HTTP 404 if database record exists but physical PDF is missing from storage.
"""
from datetime import date
from pathlib import Path

from app.models.certificate import Certificate, CertificateStatus
from app.models.job import Job, JobStatus
from app.services.certificate_generator import generate_certificate_pdf, get_safe_certificate_path


def test_get_certificate_success(client, db_session):
    """Retrieving a successfully generated certificate returns 200 with PDF bytes."""
    # 1. Create Job and Certificate in DB
    job = Job(
        event_name="Full Stack Conference",
        event_date=date(2026, 10, 15),
        status=JobStatus.COMPLETED.value,
        total_count=1,
        success_count=1,
    )
    db_session.add(job)
    db_session.commit()

    cert = Certificate(
        job_id=job.id,
        recipient_name="Ananya Rao",
        recipient_email="ananya@example.com",
        status=CertificateStatus.COMPLETED.value,
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)

    # 2. Render actual PDF on disk
    pdf_path = get_safe_certificate_path(cert.id)
    generate_certificate_pdf(
        recipient_name=cert.recipient_name,
        event_name=job.event_name,
        event_date=job.event_date,
        cert_id=cert.id,
        output_path=pdf_path,
    )

    cert.file_path = str(pdf_path)
    db_session.commit()

    # 3. Retrieve via endpoint
    response = client.get(f"/api/certificates/{cert.id}")
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    assert response.content[:5] == b"%PDF-"
    assert "attachment" in response.headers.get("content-disposition", "") or "Certificate_Ananya_Rao.pdf" in response.headers.get("content-disposition", "")

    # Cleanup
    pdf_path.unlink(missing_ok=True)


def test_get_certificate_not_found(client):
    """Querying a non-existent certificate returns 404 Not Found."""
    response = client.get("/api/certificates/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_certificate_failed_status(client, db_session):
    """Querying a certificate whose generation failed returns 400 with explanation."""
    job = Job(
        event_name="AI Summit",
        event_date=date(2026, 11, 1),
        status=JobStatus.COMPLETED_WITH_ERRORS.value,
        total_count=1,
        failure_count=1,
    )
    db_session.add(job)
    db_session.commit()

    cert = Certificate(
        job_id=job.id,
        recipient_name="Failed Candidate",
        recipient_email="failed@example.com",
        status=CertificateStatus.FAILED.value,
        error_message="Font rendering failed during canvas drawing",
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)

    response = client.get(f"/api/certificates/{cert.id}")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "failed" in detail.lower()
    assert "Font rendering failed during canvas drawing" in detail


def test_get_certificate_pending_status(client, db_session):
    """Querying a certificate that is still pending returns 409 Conflict."""
    job = Job(
        event_name="Security Workshop",
        event_date=date(2026, 11, 5),
        status=JobStatus.QUEUED.value,
        total_count=1,
    )
    db_session.add(job)
    db_session.commit()

    cert = Certificate(
        job_id=job.id,
        recipient_name="Pending Student",
        recipient_email="pending@example.com",
        status=CertificateStatus.PENDING.value,
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)

    response = client.get(f"/api/certificates/{cert.id}")
    assert response.status_code == 409
    assert "pending" in response.json()["detail"].lower()


def test_get_certificate_missing_physical_file(client, db_session):
    """If database says completed but file is absent from disk, return 404."""
    job = Job(
        event_name="Cloud Expo",
        event_date=date(2026, 11, 10),
        status=JobStatus.COMPLETED.value,
        total_count=1,
        success_count=1,
    )
    db_session.add(job)
    db_session.commit()

    cert = Certificate(
        job_id=job.id,
        recipient_name="Ghost User",
        recipient_email="ghost@example.com",
        status=CertificateStatus.COMPLETED.value,
        file_path="non_existent_directory/missing_cert.pdf",
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)

    response = client.get(f"/api/certificates/{cert.id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
