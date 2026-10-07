"""
Phase 3 Job Creation Endpoint Tests.

Tests the POST /api/jobs endpoint:
1. Returns HTTP 202 Accepted on valid input.
2. Returns correct job_id, status="queued", and total_count.
3. Correctly creates Job and Certificate records in the database.
4. Rejects malformed input with 422 and ensures no partial data is saved.
"""
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import Job, JobStatus


def test_create_job_success(client, db_session):
    """Submitting valid job creation payload returns 202 and stores job and certificates."""
    payload = {
        "event_name": "Cyber Security Workshop",
        "event_date": "2026-10-15",
        "border_style": "double",
        "border_color": "#1E3A8A",
        "border_width": 3,
        "recipients": [
            {"name": "Bhargavi Bayar", "email": "bhargavi@example.com"},
            {"name": "Rahul Kumar", "email": "rahul@example.com"}
        ]
    }

    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202

    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["total_count"] == 2

    job_id = data["job_id"]

    # Verify Job in DB (Note: FastAPI TestClient executes BackgroundTasks synchronously)
    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    assert job.event_name == "Cyber Security Workshop"
    assert str(job.event_date) == "2026-10-15"
    assert job.status == JobStatus.COMPLETED.value
    assert job.total_count == 2
    assert job.success_count == 2
    assert job.failure_count == 0
    assert job.border_style == "double"
    assert job.border_color == "#1E3A8A"
    assert job.border_width == 3

    # Verify Certificate records in DB
    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
    assert len(certs) == 2
    assert all(c.status == CertificateStatus.COMPLETED.value for c in certs)
    emails = {c.recipient_email for c in certs}
    assert emails == {"bhargavi@example.com", "rahul@example.com"}

    # Cleanup generated files
    from pathlib import Path
    for c in certs:
        if c.file_path:
            Path(c.file_path).unlink(missing_ok=True)


def test_create_job_default_border_settings(client, db_session):
    """Omitting border settings should default to double border and #1E3A8A."""
    payload = {
        "event_name": "AI Bootcamp",
        "event_date": "2026-11-01",
        "recipients": [
            {"name": "Priya Sharma", "email": "priya@example.com"}
        ]
    }

    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    job_id = data["job_id"]

    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job.border_style == "double"
    assert job.border_color == "#1E3A8A"
    assert job.border_width == 2

    # Cleanup generated files
    from pathlib import Path
    for c in job.certificates:
        if c.file_path:
            Path(c.file_path).unlink(missing_ok=True)


def test_create_job_empty_recipients_rejected(client, db_session):
    """Empty recipients array must return 422 Unprocessable Entity."""
    payload = {
        "event_name": "AI Bootcamp",
        "event_date": "2026-11-01",
        "recipients": []
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_create_job_invalid_email_rejected_and_no_leak(client, db_session):
    """An invalid recipient email must return 422 and create no records."""
    initial_jobs_count = db_session.query(Job).count()
    payload = {
        "event_name": "Web Dev Summit",
        "event_date": "2026-11-10",
        "recipients": [
            {"name": "Valid User", "email": "valid@example.com"},
            {"name": "Invalid User", "email": "not-an-email"}
        ]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422

    # Database must remain unchanged
    assert db_session.query(Job).count() == initial_jobs_count


def test_create_job_invalid_border_color_rejected(client):
    """Invalid hex color must return 422."""
    payload = {
        "event_name": "Workshop",
        "event_date": "2026-10-15",
        "border_color": "not-a-color",
        "recipients": [
            {"name": "User", "email": "user@example.com"}
        ]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422
