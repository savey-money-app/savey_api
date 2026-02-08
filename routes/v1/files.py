"""File upload routes"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from core.config import settings
from routes.v1.auth import get_user_internal_or_jwt

router = APIRouter(prefix="/files", tags=["Files"])

# Max upload size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "application/pdf",
}


class FileUploadResponse(BaseModel):
    file_id: str
    file_path: str
    filename: str
    content_type: str
    size: int


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    current_user_id: str = Depends(get_user_internal_or_jwt),
):
    """Upload a file and return its path on the shared volume."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    file_id = str(uuid.uuid4())
    upload_dir = Path(settings.UPLOADS_DIR) / file_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / (file.filename or "upload")
    dest.write_bytes(contents)

    return FileUploadResponse(
        file_id=file_id,
        file_path=str(dest),
        filename=file.filename or "upload",
        content_type=file.content_type,
        size=len(contents),
    )
