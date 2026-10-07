"""
Certificates Router.

Exposes endpoints for retrieving individual generated certificate PDFs.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.certificate import Certificate, CertificateStatus

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    summary="Download an individual generated certificate PDF",
    description=(
        "Retrieves and streams the generated PDF certificate for a recipient. "
        "Returns 404 if the certificate is not found, or 400 if certificate "
        "generation failed for this recipient."
    ),
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "The generated PDF certificate file."
        },
        400: {"description": "Certificate generation failed for this recipient."},
        404: {"description": "Certificate not found on the server."},
        409: {"description": "Certificate generation still in progress."},
    }
)
def get_certificate_file(certificate_id: int, db: Session = Depends(get_db)):
    """
    Downloads the completed PDF certificate for the given certificate ID.
    """
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()

    # 1. Certificate record does not exist
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with id {certificate_id} not found."
        )

    # 2. Certificate generation failed
    if cert.status == CertificateStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Certificate generation failed for recipient '{cert.recipient_name}'. "
                f"Reason: {cert.error_message or 'Unknown generation error'}"
            )
        )

    # 3. Certificate is still queued or processing
    if cert.status in (CertificateStatus.PENDING.value, CertificateStatus.PROCESSING.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Certificate for '{cert.recipient_name}' is currently {cert.status}. "
                "Please poll the job status and retry once processing completes."
            )
        )

    # 4. Certificate completed: verify file exists on disk
    if not cert.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file record exists but file path is missing."
        )

    file_path = Path(cert.file_path)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The generated certificate file was not found on server storage."
        )

    # Sanitize download filename for the browser
    safe_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in (" ", "_", "-")).strip()
    safe_name = safe_name.replace(" ", "_") or "recipient"
    download_filename = f"Certificate_{safe_name}.pdf"

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=download_filename,
    )
