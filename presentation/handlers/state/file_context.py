"""
File Context Manager

Manages file upload caching for reply-based workflows:
- Caching processed files by message ID
- Retrieving file context when user replies
- Auto-cleanup of old cached files
"""

import logging
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from application.services.file_processor_service import ProcessedFile

logger = logging.getLogger(__name__)

# Cache expiration
FILE_CACHE_TTL_SECONDS = 3600  # 1 hour


class FileContextManager:
    """
    Manages file context caching for reply-based file handling.

    When user sends a file without caption:
    1. File is processed and cached by message_id
    2. User can reply to that message with a task
    3. Task is enriched with cached file context

    This class handles the caching and retrieval of processed files.
    """

    def __init__(self, ttl_seconds: int = FILE_CACHE_TTL_SECONDS):
        self._cache: Dict[int, "ProcessedFile"] = {}
        self._timestamps: Dict[int, datetime] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    # === Cache Operations ===

    def cache_file(self, message_id: int, processed_file: "ProcessedFile") -> None:
        """
        Cache a processed file by message ID.

        Args:
            message_id: Telegram message ID containing the file
            processed_file: ProcessedFile object from FileProcessorService
        """
        self._cache[message_id] = processed_file
        self._timestamps[message_id] = datetime.utcnow()
        logger.debug(f"Cached file for message {message_id}: {processed_file.filename}")

        # Opportunistic cleanup of old entries
        self._cleanup_expired()

    def get_file(self, message_id: int) -> Optional["ProcessedFile"]:
        """
        Get cached file by message ID without removing it.

        Args:
            message_id: Telegram message ID to look up

        Returns:
            ProcessedFile if cached and not expired, None otherwise
        """
        if message_id not in self._cache:
            return None

        # Check expiration
        timestamp = self._timestamps.get(message_id)
        if timestamp and datetime.utcnow() - timestamp > self._ttl:
            self._remove(message_id)
            return None

        return self._cache.get(message_id)

    def pop_file(self, message_id: int) -> Optional["ProcessedFile"]:
        """
        Get and remove cached file by message ID.

        Use this when the file context is consumed (e.g., task started).

        Args:
            message_id: Telegram message ID to look up

        Returns:
            ProcessedFile if cached and not expired, None otherwise
        """
        file = self.get_file(message_id)
        if file:
            self._remove(message_id)
        return file

    def has_file(self, message_id: int) -> bool:
        """Check if file is cached for message ID"""
        return self.get_file(message_id) is not None

    # === Cleanup ===

    def _remove(self, message_id: int) -> None:
        """Remove file from cache"""
        self._cache.pop(message_id, None)
        self._timestamps.pop(message_id, None)

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache"""
        now = datetime.utcnow()
        expired = [
            msg_id for msg_id, timestamp in self._timestamps.items()
            if now - timestamp > self._ttl
        ]
        for msg_id in expired:
            self._remove(msg_id)
            logger.debug(f"Cleaned up expired file cache: {msg_id}")

    def clear_all(self) -> None:
        """Clear entire cache"""
        self._cache.clear()
        self._timestamps.clear()

    @property
    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)
