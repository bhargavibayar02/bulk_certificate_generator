"""
Phase 1 Setup & Sanity Tests.

Validates that:
1. Application starts up and health endpoints respond correctly.
2. SQLAlchemy models (Job, Certificate) persist correctly.
3. One-to-many relationship and cascading behavior work as expected.
4. Calculated properties (pending_count, progress_percentage) work accurately.
"""
from datetime import date
from app.models.job import Job, JobStatus
from app.models.certificate import Certificate, CertificateStatus


def test_root_and_health_endpoints(client):
    """Verify basic application endpoints are reachable."""
    root_response = client.get("/")
    assert root_response.status_code == 200
    root_data = root_response.json()
    assert root_data["status"] == "online"
    assert root_data["service"] == "Bulk Certificate Generator"

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "healthy"}


def test_job_model_creation_and_properties(db_session):
    """Verify Job model creation, default values, and computed properties."""
    new_job = Job(
        event_name="Full Stack Web Workshop",
        event_date=date(2026, 11, 20),
        total_count=10,
        success_count=6,
        failure_count=2,
    )
    db_session.add(new_job)
    db_session.commit()
    db_session.refresh(new_job)

    assert new_job.id is not None
    assert new_job.status == JobStatus.QUEUED.value
    assert new_job.total_count == 10
    assert new_job.success_count == 6
    assert new_job.failure_count == 2
    assert new_job.pending_count == 2
    # Progress formula: (6 + 2) / 10 * 100 = 80.0%
    assert new_job.progress_percentage == 80.0
    assert new_job.created_at is not None
    assert new_job.updated_at is not None


def test_certificate_model_and_relationship(db_session):
    """Verify Certificate model creation and 1:N relationship with Job."""
    job = Job(
        event_name="Data Science Summit",
        event_date=date(2026, 12, 1),
        total_count=2,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    cert1 = Certificate(
        job_id=job.id,
        recipient_name="Alice Smith",
        recipient_email="alice@example.com",
        status=CertificateStatus.PENDING.value,
    )
    cert2 = Certificate(
        job_id=job.id,
        recipient_name="Bob Jones",
        recipient_email="bob@example.com",
        status=CertificateStatus.PENDING.value,
    )
    db_session.add_all([cert1, cert2])
    db_session.commit()

    # Query back via relationship
    db_session.refresh(job)
    assert len(job.certificates) == 2
    recipient_names = {c.recipient_name for c in job.certificates}
    assert recipient_names == {"Alice Smith", "Bob Jones"}

    # Verify back-reference
    assert cert1.job.event_name == "Data Science Summit"
    assert cert1.status == CertificateStatus.PENDING.value
