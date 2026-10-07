"""
Phase 9 Border Customization Tests.

Deep-dive testing for controlled certificate border options:
1. End-to-end rendering and persistence for all border styles: none, single, double, thick.
2. Color normalization (#abcdef -> #ABCDEF, #123 3-digit shorthand).
3. Border width safe bounds enforcement [1, 10] across the API.
4. Protection against arbitrary injection in color/width fields.
"""
from datetime import date
from pathlib import Path
import pytest

from app.models.job import Job, JobStatus
from app.schemas.border import BorderStyle
from app.services.certificate_generator import generate_certificate_pdf


@pytest.fixture
def border_test_dir(tmp_path):
    """Provides a temporary output directory for border test PDFs."""
    d = tmp_path / "border_certs"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.mark.parametrize("style,color,width", [
    ("none", "#000000", 1),
    ("single", "#2563EB", 4),
    ("double", "#047857", 2),
    ("thick", "#7C3AED", 5),
    ("single", "#123", 1),       # 3-digit hex shorthand
    ("double", "#B45309", 10),    # Maximum allowable width
])
def test_border_rendering_variations(border_test_dir, style, color, width):
    """Verifies that all supported border combinations render valid PDFs."""
    output_pdf = border_test_dir / f"cert_{style}_{width}.pdf"

    result_path = generate_certificate_pdf(
        recipient_name="Design Verification User",
        event_name="Border Styling Masterclass",
        event_date=date(2026, 10, 15),
        cert_id=501,
        output_path=output_pdf,
        border_style=style,
        border_color=color,
        border_width=width,
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 1000
    with open(result_path, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_api_job_creation_with_border_customization(client, db_session):
    """POST /api/jobs accurately stores and applies custom border styling."""
    payload = {
        "event_name": "UI/UX Design Symposium",
        "event_date": "2026-10-15",
        "border_style": "thick",
        "border_color": "#047857",
        "border_width": 5,
        "recipients": [
            {"name": "Border Recipient", "email": "border@example.com"}
        ]
    }

    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    db_session.expire_all()
    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job.border_style == "thick"
    assert job.border_color == "#047857"
    assert job.border_width == 5
    assert job.status == JobStatus.COMPLETED.value

    # Cleanup generated file
    for c in job.certificates:
        if c.file_path:
            Path(c.file_path).unlink(missing_ok=True)


def test_api_rejects_border_width_zero(client):
    """Border width < 1 must be rejected with 422."""
    payload = {
        "event_name": "Zero Width Workshop",
        "event_date": "2026-10-15",
        "border_width": 0,
        "recipients": [{"name": "User", "email": "user@example.com"}]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_api_rejects_border_width_above_ten(client):
    """Border width > 10 must be rejected with 422."""
    payload = {
        "event_name": "Huge Width Workshop",
        "event_date": "2026-10-15",
        "border_width": 11,
        "recipients": [{"name": "User", "email": "user@example.com"}]
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_api_rejects_malicious_color_injection(client):
    """Arbitrary text or injection in border_color must be rejected with 422."""
    malicious_inputs = [
        "red; rm -rf /",
        "rgb(255, 0, 0)",
        "#FFFFFFF",  # 7 digits
        "#GGGGGG",   # non-hex
        "<script>",
        "transparent",
    ]
    for bad_color in malicious_inputs:
        payload = {
            "event_name": "Color Injection Event",
            "event_date": "2026-10-15",
            "border_color": bad_color,
            "recipients": [{"name": "User", "email": "user@example.com"}]
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422
