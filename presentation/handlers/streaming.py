"""
Streaming Handler for Telegram (Legacy re-export module)

This module re-exports from the refactored streaming package for backward compatibility.

The actual implementation is now in:
- presentation/handlers/streaming/handler.py - StreamingHandler
- presentation/handlers/streaming/formatting.py - markdown_to_html, etc.
- presentation/handlers/streaming/trackers.py - HeartbeatTracker, FileChangeTracker
- presentation/handlers/streaming/step_handler.py - StepStreamingHandler
"""

# Re-export all public API for backward compatibility
from presentation.handlers.streaming import (
    # Main handlers
    StreamingHandler,
    StepStreamingHandler,

    # Formatting utilities
    markdown_to_html,
    prepare_html_for_telegram,
    get_open_html_tags,
    StableHTMLFormatter,
    IncrementalFormatter,

    # Trackers
    ProgressTracker,
    HeartbeatTracker,
    FileChange,
    FileChangeTracker,
)

__all__ = [
    "StreamingHandler",
    "StepStreamingHandler",
    "markdown_to_html",
    "prepare_html_for_telegram",
    "get_open_html_tags",
    "StableHTMLFormatter",
    "IncrementalFormatter",
    "ProgressTracker",
    "HeartbeatTracker",
    "FileChange",
    "FileChangeTracker",
]
