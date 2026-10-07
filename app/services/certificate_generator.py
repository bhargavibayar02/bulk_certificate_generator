"""
Certificate Generation Service.

Handles physical creation and rendering of PDF certificates using ReportLab.
Ensures safe file paths, non-overlapping design, and clean separation from API routes.
"""
import uuid
from datetime import date
from pathlib import Path
from typing import List, Optional
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen.canvas import Canvas

from app.config import settings
from app.templates.certificate_template import render_certificate


def get_safe_certificate_path(cert_id: int) -> Path:
    """
    Generates a collision-free, safe file path within the configured certificate directory.
    
    Security: Uses certificate ID and random UUID hex rather than raw user-supplied
    names, completely preventing path traversal vulnerabilities.
    """
    settings.CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
    random_suffix = uuid.uuid4().hex[:8]
    safe_filename = f"certificate_{cert_id}_{random_suffix}.pdf"
    return settings.CERTIFICATES_DIR / safe_filename


def generate_certificate_pdf(
    recipient_name: str,
    event_name: str,
    event_date: date,
    cert_id: int,
    output_path: Path,
    border_style: str = "double",
    border_color: str = "#1E3A8A",
    border_width: int = 2,
    logo_paths: Optional[List[Path]] = None,
) -> Path:
    """
    Renders and writes an individual certificate PDF to the specified output path.
    
    Returns the absolute or relative Path to the successfully generated file.
    Raises an Exception if rendering fails so the caller can isolate and record errors.
    """
    # Ensure destination parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize ReportLab Canvas with landscape A4 dimensions
    canvas = Canvas(
        str(output_path),
        pagesize=landscape(A4),
        pageCompression=1
    )

    try:
        # Render the fixed visual template
        render_certificate(
            canvas=canvas,
            recipient_name=recipient_name,
            event_name=event_name,
            event_date=event_date,
            cert_id=cert_id,
            border_style=border_style,
            border_color=border_color,
            border_width=border_width,
            logo_paths=logo_paths,
        )
        canvas.showPage()
        canvas.save()
    except Exception as exc:
        # If writing failed mid-way, clean up any partially written corrupted file
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise exc

    return output_path
