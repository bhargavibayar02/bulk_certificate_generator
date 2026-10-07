"""
Phase 5 Failure Isolation & Bulk Processing Tests.

Verifies:
1. All-success bulk job processing finishes with status="completed".
2. Failure isolation: when one recipient's PDF generation fails, the remaining
   recipients continue processing uninterrupted.
3. Job status correctly transitions to "completed_with_errors".
4. Error message is stored on the failed certificate record.
5. All-failed bulk job processing correctly sets status="failed".
6. Cleanup of generated PDF files after tests.
"""
from datetime import date
from pathlib import Path
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate
from app.schemas.recipient import RecipientCreate
from app.services.job_processor import process_bulk_job
from app.services.job_service import create_bulk_job


def cleanup_certificates(certs):
    """Helper to remove generated test PDF files from disk."""
    for cert in certs:
        if cert.file_path:
            p = Path(cert.file_path)
            if p.exists():
                p.unlink(missing_ok=True)


def test_bulk_processing_all_succeed(db_session):
    """All recipients succeed -> job status becomes 'completed'."""
    job_payload = JobCreate(
        event_name="Cloud Security Workshop",
        event_date=date(2026, 10, 15),
        recipients=[
            RecipientCreate(name="Student One", email="s1@example.com"),
            RecipientCreate(name="Student Two", email="s2@example.com"),
            RecipientCreate(name="Student Three", email="s3@example.com"),
        ]
    )

    job = create_bulk_job(db_session, job_payload)
    job_id = job.id

    # Execute background processing
    process_bulk_job(job_id)

    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()

    assert updated_job.status == JobStatus.COMPLETED.value
    assert updated_job.total_count == 3
    assert updated_job.success_count == 3
    assert updated_job.failure_count == 0
    assert updated_job.pending_count == 0
    assert updated_job.progress_percentage == 100.0

    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
    assert len(certs) == 3
    for cert in certs:
        assert cert.status == CertificateStatus.COMPLETED.value
        assert cert.file_path is not None
        assert Path(cert.file_path).exists()
        assert cert.error_message is None

    cleanup_certificates(certs)


def test_failure_isolation_single_recipient_fails(db_session, monkeypatch):
    """
    Simulate deliberate failure for one recipient:
    1. First recipient succeeds.
    2. Second recipient fails (mocked exception).
    3. Third recipient succeeds (verifies execution continued).
    4. Job status becomes 'completed_with_errors'.
    """
    job_payload = JobCreate(
        event_name="AI Workshop",
        event_date=date(2026, 10, 15),
        recipients=[
            RecipientCreate(name="Alice Success", email="alice@example.com"),
            RecipientCreate(name="Bob Failure", email="bob@example.com"),
            RecipientCreate(name="Charlie Success", email="charlie@example.com"),
        ]
    )
    job = create_bulk_job(db_session, job_payload)
    job_id = job.id

    # Deliberately inject controlled failure for "Bob Failure"
    import app.services.job_processor as processor_module
    original_generate = processor_module.generate_certificate_pdf

    def mock_generate_certificate(**kwargs):
        if kwargs.get("recipient_name") == "Bob Failure":
            raise ValueError("Simulated font rendering error for Bob")
        return original_generate(**kwargs)

    monkeypatch.setattr(processor_module, "generate_certificate_pdf", mock_generate_certificate)

    # Execute processing
    process_bulk_job(job_id)

    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()

    # Job status must reflect partial success
    assert updated_job.status == JobStatus.COMPLETED_WITH_ERRORS.value
    assert updated_job.total_count == 3
    assert updated_job.success_count == 2
    assert updated_job.failure_count == 1
    assert updated_job.progress_percentage == 100.0

    # Verify individual certificate records
    certs = (
        db_session.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.id.asc())
        .all()
    )

    alice_cert = certs[0]
    bob_cert = certs[1]
    charlie_cert = certs[2]

    # Alice succeeded
    assert alice_cert.recipient_name == "Alice Success"
    assert alice_cert.status == CertificateStatus.COMPLETED.value
    assert alice_cert.file_path is not None
    assert Path(alice_cert.file_path).exists()
    assert alice_cert.error_message is None

    # Bob failed without halting execution
    assert bob_cert.recipient_name == "Bob Failure"
    assert bob_cert.status == CertificateStatus.FAILED.value
    assert bob_cert.file_path is None
    assert "Simulated font rendering error for Bob" in bob_cert.error_message

    # Charlie succeeded after Bob's failure
    assert charlie_cert.recipient_name == "Charlie Success"
    assert charlie_cert.status == CertificateStatus.COMPLETED.value
    assert charlie_cert.file_path is not None
    assert Path(charlie_cert.file_path).exists()
    assert charlie_cert.error_message is None

    cleanup_certificates(certs)


def test_bulk_processing_all_fail(db_session, monkeypatch):
    """All recipients fail -> job status becomes 'failed'."""
    job_payload = JobCreate(
        event_name="DevOps Summit",
        event_date=date(2026, 10, 15),
        recipients=[
            RecipientCreate(name="User A", email="a@example.com"),
            RecipientCreate(name="User B", email="b@example.com"),
        ]
    )
    job = create_bulk_job(db_session, job_payload)
    job_id = job.id

    import app.services.job_processor as processor_module

    def mock_all_fail(**kwargs):
        raise RuntimeError("Disk full simulation")

    monkeypatch.setattr(processor_module, "generate_certificate_pdf", mock_all_fail)

    process_bulk_job(job_id)

    db_session.expire_all()
    updated_job = db_session.query(Job).filter(Job.id == job_id).first()

    assert updated_job.status == JobStatus.FAILED.value
    assert updated_job.total_count == 2
    assert updated_job.success_count == 0
    assert updated_job.failure_count == 2
    assert updated_job.progress_percentage == 100.0


def test_end_to_end_job_creation_with_background_tasks(client, db_session):
    """
    FastAPI TestClient automatically executes BackgroundTasks synchronously.
    Verifies that calling POST /api/jobs runs the processor and produces valid files.
    """
    payload = {
        "event_name": "Full Stack Workshop",
        "event_date": "2026-10-15",
        "recipients": [
            {"name": "Dev 1", "email": "dev1@example.com"},
            {"name": "Dev 2", "email": "dev2@example.com"}
        ]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    db_session.expire_all()
    job = db_session.query(Job).filter(Job.id == job_id).first()

    # In TestClient, background task has already finished
    assert job.status == JobStatus.COMPLETED.value
    assert job.success_count == 2

    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
    cleanup_certificates(certs)
