"""
Phase 4 Certificate Generation Tests.

Tests the ReportLab PDF certificate template:
1. Verifies PDF creation, readability, and valid PDF header (%PDF-).
2. Tests all controlled border styles (none, single, double, thick).
3. Verifies safe unique file path generation (path traversal protection).
4. Cleans up all generated temporary PDF test files.
"""
from datetime import date
from pathlib import Path
import pytest

from app.services.certificate_generator import (
    generate_certificate_pdf,
    get_safe_certificate_path,
)


@pytest.fixture
def temp_cert_dir(tmp_path):
    """Provides an isolated directory for generating test PDFs."""
    output_dir = tmp_path / "test_certs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def test_generate_certificate_basic_pdf(temp_cert_dir):
    """Generates a certificate PDF and verifies it is a valid, readable PDF file."""
    output_path = temp_cert_dir / "test_cert_1.pdf"

    result_path = generate_certificate_pdf(
        recipient_name="Bhargavi Bayar",
        event_name="Cyber Security Workshop",
        event_date=date(2026, 10, 15),
        cert_id=101,
        output_path=output_path,
        border_style="double",
        border_color="#1E3A8A",
        border_width=2,
    )

    assert result_path.exists()
    assert result_path.is_file()
    assert result_path.stat().st_size > 1000  # Non-trivial size

    # Verify standard PDF file signature
    with open(result_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"


@pytest.mark.parametrize("border_style", ["none", "single", "double", "thick"])
def test_generate_certificate_all_border_styles(temp_cert_dir, border_style):
    """Ensures all 4 controlled border styles render without errors."""
    output_path = temp_cert_dir / f"cert_border_{border_style}.pdf"

    result_path = generate_certificate_pdf(
        recipient_name="Rahul Kumar",
        event_name="Cloud Architecture Seminar",
        event_date=date(2026, 11, 20),
        cert_id=202,
        output_path=output_path,
        border_style=border_style,
        border_color="#0F172A",
        border_width=3,
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 1000


def test_safe_certificate_path_format():
    """Verify generated paths use certificate ID and UUID rather than raw user names."""
    path = get_safe_certificate_path(cert_id=42)
    assert isinstance(path, Path)
    assert path.name.startswith("certificate_42_")
    assert path.name.endswith(".pdf")
    # Must not contain user-controlled special characters
    assert ".." not in str(path)


def test_generate_certificate_long_names(temp_cert_dir):
    """Verifies that unusually long recipient and event names scale cleanly without errors."""
    output_path = temp_cert_dir / "cert_long_name.pdf"

    result_path = generate_certificate_pdf(
        recipient_name="Dr. Alexander Bartholomew Montgomery-Fitzgerald III",
        event_name="International Interdisciplinary Conference on Advanced Artificial Intelligence and Quantum Technologies",
        event_date=date(2026, 12, 31),
        cert_id=999,
        output_path=output_path,
        border_style="double",
        border_color="#1E3A8A",
        border_width=2,
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 1000

