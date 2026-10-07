"""
Phase 2 Validation Tests.

Thoroughly tests Pydantic schemas and validation constraints:
1. Recipient validation (name trimming, non-empty, email format validation).
2. Event validation (event_name non-empty, trimming, event_date parsing).
3. Bulk recipients limit (empty list rejected, maximum limit enforced).
4. Border customization validation (styles, hex colors, width constraints).
"""
from datetime import date
import pytest
from pydantic import ValidationError

from app.config import settings
from app.schemas.border import BorderStyle, BorderCustomization
from app.schemas.job import JobCreate
from app.schemas.recipient import RecipientCreate


def test_recipient_valid():
    """Valid recipient data should succeed and trim whitespace."""
    recipient = RecipientCreate(
        name="  Bhargavi Bayar  ",
        email="  bhargavi@example.com  "
    )
    assert recipient.name == "Bhargavi Bayar"
    assert recipient.email == "bhargavi@example.com"


def test_recipient_empty_name():
    """Empty or whitespace-only name should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        RecipientCreate(name="   ", email="test@example.com")
    errors = str(exc_info.value)
    assert "Recipient name cannot be empty" in errors


def test_recipient_invalid_email():
    """Malformed email strings should fail validation."""
    invalid_emails = [
        "not-an-email",
        "@example.com",
        "user@",
        "user@example",
        "user space@example.com"
    ]
    for bad_email in invalid_emails:
        with pytest.raises(ValidationError):
            RecipientCreate(name="John Doe", email=bad_email)


def test_recipient_name_too_long():
    """Names exceeding the reasonable max length should fail validation."""
    with pytest.raises(ValidationError):
        RecipientCreate(name="A" * 151, email="john@example.com")


def test_job_create_valid():
    """Valid JobCreate payload should parse cleanly."""
    job_payload = JobCreate(
        event_name="  Cyber Security Workshop  ",
        event_date=date(2026, 10, 15),
        border_style=BorderStyle.DOUBLE,
        border_color="#1E3A8A",
        border_width=3,
        recipients=[
            RecipientCreate(name="Alice", email="alice@example.com"),
            RecipientCreate(name="Bob", email="bob@example.com"),
        ]
    )
    assert job_payload.event_name == "Cyber Security Workshop"
    assert job_payload.event_date == date(2026, 10, 15)
    assert job_payload.border_style == BorderStyle.DOUBLE
    assert job_payload.border_color == "#1E3A8A"
    assert job_payload.border_width == 3
    assert len(job_payload.recipients) == 2


def test_job_create_empty_event_name():
    """Empty or whitespace-only event name should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        JobCreate(
            event_name="   ",
            event_date=date(2026, 10, 15),
            recipients=[RecipientCreate(name="Alice", email="alice@example.com")]
        )
    assert "Event name cannot be empty" in str(exc_info.value)


def test_job_create_empty_recipients():
    """Job creation must require at least one recipient."""
    with pytest.raises(ValidationError):
        JobCreate(
            event_name="Workshop",
            event_date=date(2026, 10, 15),
            recipients=[]
        )


def test_job_create_exceeds_max_recipients():
    """Enforce configurable maximum recipients limit."""
    limit = settings.MAX_RECIPIENTS_PER_JOB
    recipients = [
        RecipientCreate(name=f"User {i}", email=f"user{i}@example.com")
        for i in range(limit + 1)
    ]
    with pytest.raises(ValidationError) as exc_info:
        JobCreate(
            event_name="Massive Conference",
            event_date=date(2026, 10, 15),
            recipients=recipients
        )
    assert "Maximum allowed recipients" in str(exc_info.value)


def test_border_valid_hex_colors():
    """Supported 3-digit and 6-digit hex color strings should be accepted and standardized."""
    valid_colors = ["#1E3A8A", "#ffffff", "#000", "#A1B2C3", "#123"]
    for color in valid_colors:
        border = BorderCustomization(border_color=color)
        assert border.border_color == color.upper()


def test_border_invalid_hex_colors():
    """Invalid hex strings must be rejected to prevent drawing errors."""
    invalid_colors = ["blue", "1E3A8A", "#12345", "#GGGGGG", "#1234567", "rgba(0,0,0,1)"]
    for color in invalid_colors:
        with pytest.raises(ValidationError) as exc_info:
            BorderCustomization(border_color=color)
        assert "Invalid hex color format" in str(exc_info.value)


def test_border_width_bounds():
    """Border width must be strictly within safe range [1, 10]."""
    # Safe bounds succeed
    assert BorderCustomization(border_width=1).border_width == 1
    assert BorderCustomization(border_width=10).border_width == 10

    # Below 1 fails
    with pytest.raises(ValidationError):
        BorderCustomization(border_width=0)

    # Above 10 fails
    with pytest.raises(ValidationError):
        BorderCustomization(border_width=11)


def test_border_invalid_style():
    """Unknown border styles must be rejected."""
    with pytest.raises(ValidationError):
        BorderCustomization(border_style="zigzag")  # type: ignore


def test_job_create_invalid_date():
    """Invalid date format must raise ValidationError."""
    with pytest.raises(ValidationError):
        JobCreate.model_validate({
            "event_name": "Test Event",
            "event_date": "invalid-date-string",
            "recipients": [{"name": "User", "email": "user@example.com"}]
        })


def test_job_create_missing_required_fields():
    """Missing required fields must raise ValidationError."""
    # Missing event_date
    with pytest.raises(ValidationError):
        JobCreate.model_validate({
            "event_name": "Event Without Date",
            "recipients": [{"name": "User", "email": "user@example.com"}]
        })

    # Missing recipients
    with pytest.raises(ValidationError):
        JobCreate.model_validate({
            "event_name": "Event Without Recipients",
            "event_date": "2026-10-15"
        })

