"""
Phase 8 Logo Support Tests.

Tests the optional 0-10 logo capability:
1. PDF generation with 1 logo (centered).
2. PDF generation with 2 logos (left & right).
3. PDF generation with multiple logos (3-10 distributed evenly).
4. Graceful handling of corrupted/invalid logo files without crashing PDF creation.
5. End-to-end multipart/form-data job creation with uploaded logos.
6. Rejection of > 10 logos (HTTP 400).
7. Rejection of unsupported logo file extensions (HTTP 400).
8. Rejection of logo files exceeding the 2MB size limit (HTTP 400).
"""
import io
import json
import shutil
from datetime import date
from pathlib import Path
import pytest
from PIL import Image

from app.models.certificate import Certificate
from app.models.job import Job, JobStatus
from app.services.certificate_generator import generate_certificate_pdf


def create_dummy_image_bytes(format="PNG", size=(100, 50), color=(30, 58, 138)) -> bytes:
    """Helper to generate valid in-memory image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def temp_logo_dir(tmp_path):
    """Provides a temporary directory for test logo image files."""
    d = tmp_path / "test_logos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_pdf_rendering_with_1_logo(temp_logo_dir):
    """1 logo is centered at the top."""
    logo_file = temp_logo_dir / "logo1.png"
    logo_file.write_bytes(create_dummy_image_bytes())

    output_pdf = temp_logo_dir / "cert_1_logo.pdf"
    generate_certificate_pdf(
        recipient_name="Solo Logo Recipient",
        event_name="Workshop with 1 Logo",
        event_date=date(2026, 10, 15),
        cert_id=1,
        output_path=output_pdf,
        logo_paths=[logo_file],
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000


def test_pdf_rendering_with_2_logos(temp_logo_dir):
    """2 logos placed left and right."""
    l1 = temp_logo_dir / "l1.png"
    l2 = temp_logo_dir / "l2.png"
    l1.write_bytes(create_dummy_image_bytes(color=(255, 0, 0)))
    l2.write_bytes(create_dummy_image_bytes(color=(0, 255, 0)))

    output_pdf = temp_logo_dir / "cert_2_logos.pdf"
    generate_certificate_pdf(
        recipient_name="Dual Logo Recipient",
        event_name="Workshop with 2 Logos",
        event_date=date(2026, 10, 15),
        cert_id=2,
        output_path=output_pdf,
        logo_paths=[l1, l2],
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000


def test_pdf_rendering_with_many_logos(temp_logo_dir):
    """4 logos evenly distributed across top margin."""
    logos = []
    for i in range(4):
        p = temp_logo_dir / f"logo_{i}.png"
        p.write_bytes(create_dummy_image_bytes())
        logos.append(p)

    output_pdf = temp_logo_dir / "cert_4_logos.pdf"
    generate_certificate_pdf(
        recipient_name="Multi Logo Recipient",
        event_name="Summit with 4 Logos",
        event_date=date(2026, 10, 15),
        cert_id=3,
        output_path=output_pdf,
        logo_paths=logos,
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000


def test_corrupt_logo_does_not_crash_generator(temp_logo_dir):
    """Corrupt image file should be skipped gracefully without failing PDF creation."""
    corrupt_file = temp_logo_dir / "corrupt.png"
    corrupt_file.write_bytes(b"not a real image binary data")

    output_pdf = temp_logo_dir / "cert_corrupt_logo.pdf"
    generate_certificate_pdf(
        recipient_name="Resilient Recipient",
        event_name="Resilience Test",
        event_date=date(2026, 10, 15),
        cert_id=4,
        output_path=output_pdf,
        logo_paths=[corrupt_file],
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000


def test_multipart_upload_endpoint_success(client, db_session):
    """POST /api/jobs/upload accepts multipart form data with uploaded logos."""
    img_data = create_dummy_image_bytes()
    recipients_json = json.dumps([
        {"name": "Multipart User 1", "email": "m1@example.com"},
        {"name": "Multipart User 2", "email": "m2@example.com"},
    ])

    form_data = {
        "event_name": "Multipart Conference",
        "event_date": "2026-10-15",
        "recipients": recipients_json,
        "border_style": "thick",
        "border_color": "#1E3A8A",
        "border_width": "3",
    }
    files = [
        ("logos", ("logo1.png", img_data, "image/png")),
        ("logos", ("logo2.jpg", img_data, "image/jpeg")),
    ]

    response = client.post("/api/jobs/upload", data=form_data, files=files)
    assert response.status_code == 202

    data = response.json()
    job_id = data["job_id"]
    assert data["status"] == "queued"
    assert data["total_count"] == 2

    # Verify background execution succeeded
    db_session.expire_all()
    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job.status == JobStatus.COMPLETED.value
    assert job.success_count == 2

    # Cleanup generated files and logo folders
    for cert in job.certificates:
        if cert.file_path:
            Path(cert.file_path).unlink(missing_ok=True)
    from app.services.logo_processor import get_job_logo_dir
    shutil.rmtree(get_job_logo_dir(job_id), ignore_errors=True)


def test_multipart_upload_too_many_logos(client):
    """Uploading more than 10 logos returns HTTP 400."""
    img_data = create_dummy_image_bytes()
    recipients_json = json.dumps([{"name": "User", "email": "user@example.com"}])

    form_data = {
        "event_name": "Excessive Logos Event",
        "event_date": "2026-10-15",
        "recipients": recipients_json,
    }
    # 11 logos
    files = [("logos", (f"logo{i}.png", img_data, "image/png")) for i in range(11)]

    response = client.post("/api/jobs/upload", data=form_data, files=files)
    assert response.status_code == 400
    assert "Maximum 10 logos allowed" in response.json()["detail"]


def test_multipart_upload_invalid_extension(client):
    """Uploading unsupported file extension returns HTTP 400."""
    recipients_json = json.dumps([{"name": "User", "email": "user@example.com"}])
    form_data = {
        "event_name": "Bad Ext Event",
        "event_date": "2026-10-15",
        "recipients": recipients_json,
    }
    files = [("logos", ("malicious.exe", b"executable bytes", "application/octet-stream"))]

    response = client.post("/api/jobs/upload", data=form_data, files=files)
    assert response.status_code == 400
    assert "unsupported extension" in response.json()["detail"].lower()


def test_multipart_upload_file_too_large(client):
    """Uploading a logo > 2MB returns HTTP 400."""
    recipients_json = json.dumps([{"name": "User", "email": "user@example.com"}])
    form_data = {
        "event_name": "Big Logo Event",
        "event_date": "2026-10-15",
        "recipients": recipients_json,
    }
    # 2.5 MB fake png
    large_data = b"x" * (int(2.5 * 1024 * 1024))
    files = [("logos", ("huge.png", large_data, "image/png"))]

    response = client.post("/api/jobs/upload", data=form_data, files=files)
    assert response.status_code == 400
    assert "exceeds maximum allowed size" in response.json()["detail"].lower()
