"""
Callback Handlers Package

Refactored from monolithic callbacks.py (2600+ lines) into specialized modules.

Structure:
- base.py - BaseCallbackHandler with common functionality
- docker.py - Docker container management
- claude.py - Claude Code HITL (permissions, questions, plans)
- project.py - Project management (TODO)
- context.py - Context/session management (TODO)
- variables.py - Context variables management (TODO)
- plugins.py - Plugin management (TODO)

For backwards compatibility, CallbackHandlers class delegates to specialized handlers.
"""

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.handlers.callbacks.docker import DockerCallbackHandler
from presentation.handlers.callbacks.claude import ClaudeCallbackHandler

# Re-export from legacy module for backwards compatibility
from presentation.handlers.callbacks.legacy import CallbackHandlers, register_handlers

__all__ = [
    'BaseCallbackHandler',
    'DockerCallbackHandler',
    'ClaudeCallbackHandler',
    'CallbackHandlers',
    'register_handlers',
]
