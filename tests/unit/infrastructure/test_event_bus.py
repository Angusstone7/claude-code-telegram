"""Unit tests for EventBus."""

import asyncio

import pytest
from unittest.mock import AsyncMock

from infrastructure.websocket.event_bus import EventBus


class TestEventBusSubscribePublish:
    """Tests for basic subscribe/publish functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """Test that a subscriber receives published events."""
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe("test_channel", "sub1", handler)
        await bus.publish("test_channel", {"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_event(self):
        """Test that all subscribers on a channel receive the event."""
        bus = EventBus()
        received_a = []
        received_b = []

        async def handler_a(data):
            received_a.append(data)

        async def handler_b(data):
            received_b.append(data)

        bus.subscribe("channel", "sub_a", handler_a)
        bus.subscribe("channel", "sub_b", handler_b)

        await bus.publish("channel", {"msg": "hello"})

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert received_a[0] == {"msg": "hello"}
        assert received_b[0] == {"msg": "hello"}

    @pytest.mark.asyncio
    async def test_publish_to_empty_channel(self):
        """Test that publishing to a channel with no subscribers does not raise."""
        bus = EventBus()
        await bus.publish("empty_channel", {"data": 1})
        # No error means success

    @pytest.mark.asyncio
    async def test_subscriber_error_does_not_propagate(self):
        """Test that an error in one subscriber does not affect others."""
        bus = EventBus()
        received = []

        async def bad_handler(data):
            raise RuntimeError("Subscriber error")

        async def good_handler(data):
            received.append(data)

        bus.subscribe("channel", "bad", bad_handler)
        bus.subscribe("channel", "good", good_handler)

        await bus.publish("channel", {"test": True})

        # Good handler should still receive the event
        assert len(received) == 1


class TestEventBusUnsubscribe:
    """Tests for unsubscribe functionality."""

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_delivery(self):
        """Test that unsubscribed handler no longer receives events."""
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe("channel", "sub1", handler)
        await bus.publish("channel", {"msg": "first"})
        assert len(received) == 1

        bus.unsubscribe("channel", "sub1")
        await bus.publish("channel", {"msg": "second"})

        # Should still have only the first message
        assert len(received) == 1
        assert received[0]["msg"] == "first"

    @pytest.mark.asyncio
    async def test_unsubscribe_only_removes_specified(self):
        """Test that unsubscribe only removes the specified subscriber."""
        bus = EventBus()
        received_a = []
        received_b = []

        async def handler_a(data):
            received_a.append(data)

        async def handler_b(data):
            received_b.append(data)

        bus.subscribe("channel", "sub_a", handler_a)
        bus.subscribe("channel", "sub_b", handler_b)

        bus.unsubscribe("channel", "sub_a")
        await bus.publish("channel", {"msg": "after_unsub"})

        assert len(received_a) == 0
        assert len(received_b) == 1

    def test_unsubscribe_nonexistent_does_not_raise(self):
        """Test that unsubscribing a non-existent subscriber does not raise."""
        bus = EventBus()
        bus.unsubscribe("channel", "nonexistent")  # Should not raise


class TestEventBusPublishAndWait:
    """Tests for publish_and_wait with first-response-wins pattern."""

    @pytest.mark.asyncio
    async def test_publish_and_wait_receives_response(self):
        """Test that publish_and_wait returns the first response."""
        bus = EventBus()

        async def responder(data):
            request_id = data.get("request_id")
            if request_id:
                await bus.respond(request_id, {"answer": 42}, "responder1")

        bus.subscribe("requests", "resp1", responder)

        result = await bus.publish_and_wait(
            channel="requests",
            request_id="req-001",
            data={"question": "what?"},
            timeout=5.0,
        )

        assert result is not None
        assert result["answer"] == 42

    @pytest.mark.asyncio
    async def test_publish_and_wait_timeout(self):
        """Test that publish_and_wait returns None on timeout."""
        bus = EventBus()

        # No subscriber will respond
        async def silent_handler(data):
            pass

        bus.subscribe("requests", "silent", silent_handler)

        result = await bus.publish_and_wait(
            channel="requests",
            request_id="req-timeout",
            data={"question": "hello?"},
            timeout=0.1,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_publish_and_wait_cleans_pending_after_response(self):
        """Test that pending request is removed after response."""
        bus = EventBus()

        async def responder(data):
            request_id = data.get("request_id")
            if request_id:
                await bus.respond(request_id, {"ok": True}, "resp1")

        bus.subscribe("ch", "resp1", responder)

        assert bus.pending_count == 0
        await bus.publish_and_wait("ch", "req-clean", {"data": 1}, timeout=5.0)
        assert bus.pending_count == 0

    @pytest.mark.asyncio
    async def test_publish_and_wait_cleans_pending_after_timeout(self):
        """Test that pending request is removed after timeout."""
        bus = EventBus()

        async def noop(data):
            pass

        bus.subscribe("ch", "noop", noop)

        await bus.publish_and_wait("ch", "req-timeout-clean", {}, timeout=0.1)
        assert bus.pending_count == 0

    @pytest.mark.asyncio
    async def test_publish_and_wait_data_includes_request_id(self):
        """Test that the published data includes the request_id."""
        bus = EventBus()
        received_data = []

        async def capture(data):
            received_data.append(data)

        bus.subscribe("ch", "cap", capture)

        # Use a short timeout since no one responds
        await bus.publish_and_wait("ch", "req-check-id", {"orig": "data"}, timeout=0.1)

        assert len(received_data) == 1
        assert received_data[0]["request_id"] == "req-check-id"
        assert received_data[0]["orig"] == "data"


class TestEventBusRespond:
    """Tests for the respond method."""

    @pytest.mark.asyncio
    async def test_respond_returns_false_for_unknown_request(self):
        """Test that respond returns False for a non-existent request_id."""
        bus = EventBus()

        result = await bus.respond("unknown-req", {"data": 1}, "resp1")

        assert result is False

    @pytest.mark.asyncio
    async def test_respond_returns_false_for_already_resolved(self):
        """Test that second response to same request returns False."""
        bus = EventBus()
        results = []

        async def first_responder(data):
            request_id = data.get("request_id")
            if request_id:
                r = await bus.respond(request_id, {"from": "first"}, "resp1")
                results.append(("first", r))

        async def second_responder(data):
            request_id = data.get("request_id")
            if request_id:
                # Small delay to ensure first responder wins
                await asyncio.sleep(0.05)
                r = await bus.respond(request_id, {"from": "second"}, "resp2")
                results.append(("second", r))

        bus.subscribe("ch", "resp1", first_responder)
        bus.subscribe("ch", "resp2", second_responder)

        response = await bus.publish_and_wait("ch", "req-dup", {}, timeout=5.0)

        assert response == {"from": "first"}

        # Wait a bit for the second responder to complete
        await asyncio.sleep(0.1)

        # First should succeed, second should fail
        first_results = [r for name, r in results if name == "first"]
        second_results = [r for name, r in results if name == "second"]
        assert first_results[0] is True
        assert second_results[0] is False


class TestEventBusPendingCount:
    """Tests for pending_count property."""

    def test_pending_count_initially_zero(self):
        """Test that pending_count is 0 initially."""
        bus = EventBus()
        assert bus.pending_count == 0

    @pytest.mark.asyncio
    async def test_pending_count_during_wait(self):
        """Test that pending_count reflects active requests."""
        bus = EventBus()
        count_during = []

        async def check_count(data):
            count_during.append(bus.pending_count)
            # Don't respond, let it timeout

        bus.subscribe("ch", "counter", check_count)

        await bus.publish_and_wait("ch", "req-count", {}, timeout=0.1)

        assert count_during[0] == 1
        assert bus.pending_count == 0  # Cleaned up after timeout
