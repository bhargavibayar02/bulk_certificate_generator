"""
Phase 6 Job Status & Progress Tracking Tests.

Tests the progress monitoring endpoints:
1. GET /api/jobs/{job_id} returns accurate progress metrics.
2. Progress formula ((success + failure) / total * 100) and pending_count calculate accurately.
3. GET /api/jobs/{job_id} returns 404 for non-existent job.
4. GET /api/jobs/{job_id}/certificates lists all certificates with metadata (no binary PDF).
5. GET /api/jobs/{job_id}/certificates returns 404 for non-existent job.
"""
from datetime import date
from pathlib import Path

from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate
from app.schemas.recipient import RecipientCreate
from app.services.job_processor import process_bulk_job
from app.services.job_service import create_bulk_job


def cleanup_job_files(job):
    """Helper to remove created PDFs."""
    for cert in job.certificates:
        if cert.file_path:
            Path(cert.file_path).unlink(missing_ok=True)


def test_get_job_status_completed(client, db_session):
    """Querying a completed job returns 200 with 100% progress."""
    job_payload = JobCreate(
        event_name="Data Engineering Bootcamp",
        event_date=date(2026, 10, 15),
        recipients=[
            RecipientCreate(name="Candidate 1", email="c1@example.com"),
            RecipientCreate(name="Candidate 2", email="c2@example.com"),
        ]
    )
    job = create_bulk_job(db_session, job_payload)
    job_id = job.id

    process_bulk_job(job_id)

    db_session.expire_all()
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == JobStatus.COMPLETED.value
    assert data["total_count"] == 2
    assert data["success_count"] == 2
    assert data["failure_count"] == 0
    assert data["pending_count"] == 0
    assert data["progress_percentage"] == 100.0
    assert data["event_name"] == "Data Engineering Bootcamp"

    db_session.refresh(job)
    cleanup_job_files(job)


def test_get_job_status_in_progress_formula(client, db_session):
    """
    Verifies progress calculation formula during active processing:
    (success_count + failure_count) / total_count * 100
    """
    # Create job with simulated intermediate progress
    job = Job(
        event_name="Machine Learning Expo",
        event_date=date(2026, 12, 1),
        status=JobStatus.PROCESSING.value,
        total_count=10,
        success_count=7,
        failure_count=1,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == job.id
    assert data["status"] == "processing"
    assert data["total_count"] == 10
    assert data["success_count"] == 7
    assert data["failure_count"] == 1
    # 10 - (7 + 1) = 2 pending
    assert data["pending_count"] == 2
    # (7 + 1) / 10 * 100 = 80.0%
    assert data["progress_percentage"] == 80.0


def test_get_job_status_not_found(client):
    """Non-existent job ID returns 404 Not Found."""
    response = client.get("/api/jobs/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_job_certificates_success(client, db_session):
    """GET /api/jobs/{job_id}/certificates lists recipient records without binary content."""
    job_payload = JobCreate(
        event_name="Webinar on APIs",
        event_date=date(2026, 10, 20),
        recipients=[
            RecipientCreate(name="Student Alpha", email="alpha@example.com"),
            RecipientCreate(name="Student Beta", email="beta@example.com"),
        ]
    )
    job = create_bulk_job(db_session, job_payload)
    job_id = job.id

    response = client.get(f"/api/jobs/{job_id}/certificates")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    first_cert = data[0]
    assert "id" in first_cert
    assert first_cert["job_id"] == job_id
    assert first_cert["recipient_name"] == "Student Alpha"
    assert first_cert["recipient_email"] == "alpha@example.com"
    assert first_cert["status"] == "pending"
    assert "error_message" in first_cert
    # Ensure binary content is not returned
    assert "content" not in first_cert
    assert "pdf" not in first_cert


def test_list_job_certificates_not_found(client):
    """Listing certificates for non-existent job ID returns 404 Not Found."""
    response = client.get("/api/jobs/888888/certificates")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
