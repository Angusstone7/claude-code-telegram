"""
File Context Manager

Manages file upload caching for reply-based workflows:
- Caching processed files by message ID
- Caching multiple files (media groups) by message ID
- Retrieving file context when user replies
- Auto-cleanup of old cached files
"""

import logging
from typing import Optional, Dict, List, Union, TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from application.services.file_processor_service import ProcessedFile

logger = logging.getLogger(__name__)

# Cache expiration
FILE_CACHE_TTL_SECONDS = 3600  # 1 hour

# Type alias for cached files - can be single file or list of files
CachedFiles = Union["ProcessedFile", List["ProcessedFile"]]


class FileContextManager:
    """
    Manages file context caching for reply-based file handling.

    When user sends a file without caption:
    1. File is processed and cached by message_id
    2. User can reply to that message with a task
    3. Task is enriched with cached file context

    Supports both single files and media groups (albums).

    This class handles the caching and retrieval of processed files.
    """

    def __init__(self, ttl_seconds: int = FILE_CACHE_TTL_SECONDS):
        self._cache: Dict[int, CachedFiles] = {}
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

    # === Multiple Files (Media Groups) Support ===

    def cache_files(self, message_id: int, files: List["ProcessedFile"]) -> None:
        """
        Cache multiple processed files by message ID.

        Used for media groups (albums) when user sends multiple files at once.

        Args:
            message_id: Telegram message ID of the bot's response
            files: List of ProcessedFile objects
        """
        if not files:
            return

        if len(files) == 1:
            # Single file - use standard cache
            self.cache_file(message_id, files[0])
        else:
            # Multiple files - cache as list
            self._cache[message_id] = files
            self._timestamps[message_id] = datetime.utcnow()
            filenames = [f.filename for f in files]
            logger.debug(f"Cached {len(files)} files for message {message_id}: {filenames}")

        self._cleanup_expired()

    def get_files(self, message_id: int) -> Optional[List["ProcessedFile"]]:
        """
        Get cached files by message ID without removing them.

        Always returns a list (even for single cached file).

        Args:
            message_id: Telegram message ID to look up

        Returns:
            List of ProcessedFile if cached and not expired, None otherwise
        """
        if message_id not in self._cache:
            return None

        # Check expiration
        timestamp = self._timestamps.get(message_id)
        if timestamp and datetime.utcnow() - timestamp > self._ttl:
            self._remove(message_id)
            return None

        cached = self._cache.get(message_id)
        if cached is None:
            return None

        # Always return as list
        if isinstance(cached, list):
            return cached
        else:
            return [cached]

    def pop_files(self, message_id: int) -> Optional[List["ProcessedFile"]]:
        """
        Get and remove cached files by message ID.

        Use this when the file context is consumed (e.g., task started).

        Args:
            message_id: Telegram message ID to look up

        Returns:
            List of ProcessedFile if cached and not expired, None otherwise
        """
        files = self.get_files(message_id)
        if files:
            self._remove(message_id)
        return files

    def has_files(self, message_id: int) -> bool:
        """Check if files are cached for message ID"""
        return self.get_files(message_id) is not None

    def get_files_count(self, message_id: int) -> int:
        """Get count of cached files for message ID"""
        files = self.get_files(message_id)
        return len(files) if files else 0
