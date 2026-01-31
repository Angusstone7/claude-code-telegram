"""
Streaming module for Telegram message updates.

This module handles real-time streaming of Claude Code output to Telegram:
- Rate-limited message updates via MessageUpdateCoordinator
- Markdown to HTML conversion with streaming support
- Progress tracking with animated spinners
- File change tracking for session summaries

Main components:
- StreamingHandler: Main streaming controller
- StepStreamingHandler: Step-by-step tool status display
- HeartbeatTracker: Periodic status updates with animation
- FileChangeTracker: Track file modifications for summary
"""

# Main handler
from presentation.handlers.streaming.handler import StreamingHandler

# Formatting utilities
from presentation.handlers.streaming.formatting import (
    markdown_to_html,
    prepare_html_for_telegram,
    get_open_html_tags,
    StableHTMLFormatter,
    IncrementalFormatter,
)

# Trackers
from presentation.handlers.streaming.trackers import (
    ProgressTracker,
    HeartbeatTracker,
    FileChange,
    FileChangeTracker,
)

# Step handler
from presentation.handlers.streaming.step_handler import StepStreamingHandler

__all__ = [
    # Main
    "StreamingHandler",
    "StepStreamingHandler",

    # Formatting
    "markdown_to_html",
    "prepare_html_for_telegram",
    "get_open_html_tags",
    "StableHTMLFormatter",
    "IncrementalFormatter",

    # Trackers
    "ProgressTracker",
    "HeartbeatTracker",
    "FileChange",
    "FileChangeTracker",
]
