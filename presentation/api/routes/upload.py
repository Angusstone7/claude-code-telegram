"""
File upload endpoint for chat attachments.

POST /api/v1/files/upload - Upload a file to be used as Claude context.
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel

from presentation.api.security import hybrid_auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed extensions
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".html", ".css", ".scss", ".less",
    ".java", ".kt", ".go", ".rs", ".rb", ".php",
    ".c", ".cpp", ".h", ".hpp",
    ".sh", ".bash", ".zsh",
    ".sql", ".graphql",
    ".xml", ".csv",
    ".dockerfile", ".gitignore", ".env.example",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".pdf",
    ".log",
}

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/claude_uploads")


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    content_type: str | None
    path: str


@router.post("/files/upload", response_model=UploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(hybrid_auth),
):
    """Upload a file for use as Claude context."""
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' is not allowed")

    # Read content with size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            413,
            f"File too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Generate unique filename
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{file.filename or 'unnamed'}"

    # Ensure upload dir exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save file
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(
        "File uploaded: %s (%d bytes) by user %s",
        safe_name,
        len(content),
        user.get("user_id", "unknown"),
    )

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "unnamed",
        size=len(content),
        content_type=file.content_type,
        path=file_path,
    )
