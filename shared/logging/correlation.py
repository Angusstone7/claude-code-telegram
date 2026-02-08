"""
Correlation ID context for request tracing.

Uses contextvars to propagate correlation_id across async call chain.
Every incoming Telegram update or HTTP request gets a unique ID
that appears in all log lines produced during its processing.

Usage:
    from shared.logging.correlation import get_correlation_id, set_correlation_id

    # Middleware sets it automatically
    # To read in any async code:
    cid = get_correlation_id()
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable — automatically propagated through asyncio tasks
_correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Get current correlation_id (or None if not set)."""
    return _correlation_id_var.get()


def set_correlation_id(cid: str) -> None:
    """Set correlation_id for the current async context."""
    _correlation_id_var.set(cid)


def generate_correlation_id(prefix: str = "") -> str:
    """
    Generate a new correlation_id.

    Format: {prefix}{short_uuid}
    Example: tg-a1b2c3d4, api-e5f6g7h8
    """
    short = uuid.uuid4().hex[:8]
    return f"{prefix}{short}" if prefix else short
