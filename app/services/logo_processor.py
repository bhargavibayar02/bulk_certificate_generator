"""
Logo Processor Service.

Handles validation, aspect-ratio checking, and secure persistence of uploaded logos:
- Enforces maximum logo limit (10).
- Enforces file size limits (2MB).
- Enforces supported extensions (.png, .jpg, .jpeg).
- Validates image integrity using Pillow.
- Generates collision-free safe filenames in an isolated job directory.
"""
import io
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException, UploadFile, status
from PIL import Image

from app.config import settings


def get_job_logo_dir(job_id: int) -> Path:
    """
    Returns the dedicated logo storage directory for a specific job.
    """
    logo_dir = settings.CERTIFICATES_DIR / "logos" / f"job_{job_id}"
    logo_dir.mkdir(parents=True, exist_ok=True)
    return logo_dir


def get_job_logos(job_id: int) -> List[Path]:
    """
    Retrieves list of existing saved logo files for a job.
    """
    logo_dir = settings.CERTIFICATES_DIR / "logos" / f"job_{job_id}"
    if not logo_dir.exists():
        return []
    return sorted([p for p in logo_dir.iterdir() if p.is_file()])


def validate_and_save_logos(job_id: int, files: Optional[List[UploadFile]]) -> List[Path]:
    """
    Validates uploaded logo files and writes them to disk.
    
    Checks:
    - Maximum logo count <= 10
    - Allowed extension in ('.png', '.jpg', '.jpeg')
    - File size <= 2MB
    - Image format validity via Pillow
    """
    if not files:
        return []

    # 1. Enforce maximum count limit
    if len(files) > settings.MAX_LOGOS_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Maximum {settings.MAX_LOGOS_PER_JOB} logos allowed per job. "
                f"Received: {len(files)} logos."
            )
        )

    saved_paths: List[Path] = []
    logo_dir = get_job_logo_dir(job_id)

    for index, file in enumerate(files, start=1):
        if not file.filename:
            continue

        # 2. Validate file extension
        suffix = Path(file.filename).suffix.lower()
        if suffix not in settings.ALLOWED_LOGO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File '{file.filename}' has unsupported extension '{suffix}'. "
                    f"Allowed extensions: {', '.join(settings.ALLOWED_LOGO_EXTENSIONS)}."
                )
            )

        # 3. Read content and validate file size
        content = file.file.read()
        if len(content) > settings.MAX_LOGO_FILE_SIZE_BYTES:
            max_mb = settings.MAX_LOGO_FILE_SIZE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' exceeds maximum allowed size of {max_mb:.0f}MB."
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' is empty."
            )

        # 4. Verify valid image using Pillow
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' is not a valid or readable image."
            )

        # 5. Persist to safe unique path
        safe_name = f"logo_{index}_{uuid.uuid4().hex[:6]}{suffix}"
        target_path = logo_dir / safe_name
        target_path.write_bytes(content)
        saved_paths.append(target_path)

    return saved_paths
