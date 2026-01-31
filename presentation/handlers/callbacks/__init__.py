"""
Callback Handlers Package

Refactored from monolithic callbacks.py (2600+ lines) into specialized modules.

Structure:
- base.py - BaseCallbackHandler with common functionality
- docker.py - Docker container management callbacks
- claude.py - Claude Code HITL (permissions, questions, plans)
- project.py - Project management and file browser
- context.py - Context/session management
- variables.py - Context and global variables management
- legacy.py - Remaining handlers (plugins, etc.) - to be further refactored

For backwards compatibility, CallbackHandlers class delegates to specialized handlers.
"""

from presentation.handlers.callbacks.base import BaseCallbackHandler
from presentation.handlers.callbacks.docker import DockerCallbackHandler
from presentation.handlers.callbacks.claude import ClaudeCallbackHandler
from presentation.handlers.callbacks.project import ProjectCallbackHandler
from presentation.handlers.callbacks.context import ContextCallbackHandler
from presentation.handlers.callbacks.variables import VariableCallbackHandler
from presentation.handlers.callbacks.plugins import PluginCallbackHandler

# Re-export from legacy module for backwards compatibility
from presentation.handlers.callbacks.legacy import CallbackHandlers, register_handlers

__all__ = [
    'BaseCallbackHandler',
    'DockerCallbackHandler',
    'ClaudeCallbackHandler',
    'ProjectCallbackHandler',
    'ContextCallbackHandler',
    'VariableCallbackHandler',
    'PluginCallbackHandler',
    'CallbackHandlers',
    'register_handlers',
]
