"""File browser API routes.

Provides endpoints for browsing the file system within /root/projects
and creating new directories.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from presentation.api.security import hybrid_auth
from presentation.api.schemas.files import (
    FileEntry,
    FileBrowserResponse,
    MkdirRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["File Browser"])

# Allowed base path — all operations must stay within this directory
ALLOWED_BASE = "/root/projects"


def _canonicalize(path: str) -> str:
    """Return the canonical absolute path."""
    return os.path.normpath(os.path.abspath(path))


def _is_safe_path(path: str) -> bool:
    """Check that the canonical path is within ALLOWED_BASE."""
    canon = _canonicalize(path)
    base = _canonicalize(ALLOWED_BASE)
    return canon == base or canon.startswith(base + os.sep)


@router.get(
    "/browse",
    response_model=FileBrowserResponse,
    summary="Browse directory",
    description="List directory contents. Path must be under /root/projects.",
)
async def browse_directory(
    path: str = Query(ALLOWED_BASE, description="Directory path to browse"),
    user: dict = Depends(hybrid_auth),
) -> FileBrowserResponse:
    """List directory entries with metadata."""
    canon = _canonicalize(path)

    if not _is_safe_path(canon):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: path must be under {ALLOWED_BASE}",
        )

    if not os.path.isdir(canon):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {path}",
        )

    entries: list[FileEntry] = []
    try:
        for entry in os.scandir(canon):
            # Skip hidden files/directories
            if entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
                size = stat.st_size if entry.is_file() else None
                modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                entries.append(
                    FileEntry(
                        name=entry.name,
                        path=entry.path,
                        is_directory=entry.is_dir(),
                        size=size,
                        modified_at=modified_at,
                    )
                )
            except OSError:
                continue

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied reading: {path}",
        )
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading directory: {exc}",
        )

    # Sort: directories first, then alphabetically
    entries.sort(key=lambda e: (not e.is_directory, e.name.lower()))

    # Determine parent path
    base = _canonicalize(ALLOWED_BASE)
    parent_path: Optional[str] = None
    if canon != base:
        parent = os.path.dirname(canon)
        if _is_safe_path(parent):
            parent_path = parent

    return FileBrowserResponse(
        current_path=canon,
        parent_path=parent_path,
        entries=entries,
    )


@router.post(
    "/mkdir",
    response_model=FileBrowserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create directory",
    description="Create a new directory. Path must be under /root/projects.",
)
async def create_directory(
    request: MkdirRequest,
    user: dict = Depends(hybrid_auth),
) -> FileBrowserResponse:
    """Create a new directory and return the parent's listing."""
    canon = _canonicalize(request.path)

    if not _is_safe_path(canon):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: path must be under {ALLOWED_BASE}",
        )

    if os.path.exists(canon):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Path already exists: {request.path}",
        )

    try:
        os.makedirs(canon, exist_ok=False)
        logger.info("Directory created: %s (user=%s)", canon, user.get("user_id"))
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create directory: {exc}",
        )

    # Return parent directory listing
    parent = os.path.dirname(canon)
    return await browse_directory(path=parent, user=user)
