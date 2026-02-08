"""Tests for correlation ID module."""

import pytest
from shared.logging.correlation import (
    get_correlation_id,
    set_correlation_id,
    generate_correlation_id,
)


class TestCorrelationId:
    """Tests for correlation_id contextvars."""

    def test_default_is_none(self):
        """correlation_id is None by default."""
        # Reset to default
        set_correlation_id(None)
        assert get_correlation_id() is None

    def test_set_and_get(self):
        """Can set and retrieve correlation_id."""
        set_correlation_id("test-abc123")
        assert get_correlation_id() == "test-abc123"
        # Cleanup
        set_correlation_id(None)

    def test_generate_with_prefix(self):
        """generate_correlation_id produces {prefix}{8hex}."""
        cid = generate_correlation_id("tg-")
        assert cid.startswith("tg-")
        assert len(cid) == 11  # "tg-" + 8 hex chars

    def test_generate_without_prefix(self):
        """generate_correlation_id without prefix produces 8 hex chars."""
        cid = generate_correlation_id()
        assert len(cid) == 8
        assert all(c in "0123456789abcdef" for c in cid)

    def test_generate_unique(self):
        """Each call generates a unique ID."""
        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100

    def test_api_prefix(self):
        """API prefix works correctly."""
        cid = generate_correlation_id("api-")
        assert cid.startswith("api-")
        assert len(cid) == 12  # "api-" + 8 hex chars
