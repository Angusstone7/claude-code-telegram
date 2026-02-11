"""Smoke test: concurrent WebSocket connections (SC-008).

Validates that ConnectionManager and EventBus handle concurrent
connections correctly without a running server — pure unit-level checks
against the actual production classes.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from infrastructure.websocket.connection_manager import ConnectionManager
from infrastructure.websocket.event_bus import EventBus


def _make_ws() -> MagicMock:
    """Create a mock WebSocket with accept() and send_json()."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# ConnectionManager — concurrent connections
# ---------------------------------------------------------------------------


class TestConcurrentConnections:
    """SC-008: 5 simultaneous connections for different users."""

    @pytest.mark.asyncio
    async def test_five_users_connect_concurrently(self):
        """5 different users connect at the same time."""
        manager = ConnectionManager()
        users = [f"user_{i}" for i in range(5)]
        websockets = [_make_ws() for _ in range(5)]

        # Connect all 5 concurrently
        tasks = [
            manager.connect(ws, uid, f"session_{uid}")
            for ws, uid in zip(websockets, users)
        ]
        connections = await asyncio.gather(*tasks)

        assert manager.total_connections == 5
        assert set(manager.connected_users) == set(users)

        # Each websocket was accepted
        for ws in websockets:
            ws.accept.assert_awaited_once()

        # All connections are valid
        for conn, uid in zip(connections, users):
            assert conn.user_id == uid

    @pytest.mark.asyncio
    async def test_broadcast_reaches_all_concurrent_users(self):
        """Broadcasting a message reaches all 5 connected users."""
        manager = ConnectionManager()
        websockets = []
        for i in range(5):
            ws = _make_ws()
            websockets.append(ws)
            await manager.connect(ws, f"user_{i}", f"session_{i}")

        message = {"type": "notification", "text": "hello everyone"}
        sent = await manager.broadcast(message)

        assert sent == 5
        for ws in websockets:
            ws.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_disconnect_one_does_not_affect_others(self):
        """Disconnecting one user out of 5 keeps the other 4 intact."""
        manager = ConnectionManager()
        connections = []
        for i in range(5):
            ws = _make_ws()
            conn = await manager.connect(ws, f"user_{i}", f"session_{i}")
            connections.append(conn)

        # Disconnect user_2
        await manager.disconnect(connections[2])

        assert manager.total_connections == 4
        assert not manager.is_user_connected("user_2")

        # The remaining 4 are still connected
        for i in [0, 1, 3, 4]:
            assert manager.is_user_connected(f"user_{i}")

        # Broadcasting still works for remaining 4
        message = {"type": "update"}
        sent = await manager.broadcast(message)
        assert sent == 4

    @pytest.mark.asyncio
    async def test_multiple_sessions_per_user(self):
        """A single user with 3 concurrent sessions receives messages on all."""
        manager = ConnectionManager()
        websockets = []
        for i in range(3):
            ws = _make_ws()
            websockets.append(ws)
            await manager.connect(ws, "alice", f"tab_{i}")

        assert manager.total_connections == 3
        assert len(manager.connected_users) == 1

        message = {"type": "data", "payload": "sync"}
        sent = await manager.send_to_user("alice", message)

        assert sent == 3
        for ws in websockets:
            ws.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_concurrent_send_and_disconnect(self):
        """Sending messages while connections drop does not crash."""
        manager = ConnectionManager()

        # 3 good + 2 dead
        good_ws = [_make_ws() for _ in range(3)]
        dead_ws = [_make_ws() for _ in range(2)]
        for ws in dead_ws:
            ws.send_json = AsyncMock(side_effect=ConnectionError("gone"))

        for i, ws in enumerate(good_ws):
            await manager.connect(ws, f"good_{i}", f"s_{i}")
        for i, ws in enumerate(dead_ws):
            await manager.connect(ws, f"dead_{i}", f"s_{i}")

        assert manager.total_connections == 5

        message = {"type": "test"}
        sent = await manager.broadcast(message)

        # Only 3 good connections should have received
        assert sent == 3
        # Dead connections should be cleaned up
        assert manager.total_connections == 3
        for i in range(2):
            assert not manager.is_user_connected(f"dead_{i}")


# ---------------------------------------------------------------------------
# EventBus — concurrent subscriptions
# ---------------------------------------------------------------------------


class TestConcurrentEventBus:
    """EventBus handles concurrent publish/subscribe correctly."""

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_event(self):
        """All subscribers on a channel receive the published event."""
        bus = EventBus()
        received = []

        for i in range(5):
            async def handler(data, idx=i):
                received.append((idx, data))

            bus.subscribe("updates", f"sub_{i}", handler)

        await bus.publish("updates", {"msg": "hello"})

        assert len(received) == 5
        # Each subscriber got the same data
        for idx, data in received:
            assert data == {"msg": "hello"}

    @pytest.mark.asyncio
    async def test_unsubscribe_does_not_affect_others(self):
        """Unsubscribing one listener does not affect remaining ones."""
        bus = EventBus()
        results = []

        async def handler_a(data):
            results.append("a")

        async def handler_b(data):
            results.append("b")

        async def handler_c(data):
            results.append("c")

        bus.subscribe("ch", "sub_a", handler_a)
        bus.subscribe("ch", "sub_b", handler_b)
        bus.subscribe("ch", "sub_c", handler_c)

        bus.unsubscribe("ch", "sub_b")

        await bus.publish("ch", {})

        assert sorted(results) == ["a", "c"]

    @pytest.mark.asyncio
    async def test_publish_and_wait_first_response_wins(self):
        """publish_and_wait returns the first response and ignores later ones."""
        bus = EventBus()
        request_id = "req-001"

        async def fast_responder(data):
            # Respond immediately
            rid = data.get("request_id")
            if rid:
                await bus.respond(rid, {"answer": "fast"}, "responder_fast")

        async def slow_responder(data):
            await asyncio.sleep(0.05)
            rid = data.get("request_id")
            if rid:
                await bus.respond(rid, {"answer": "slow"}, "responder_slow")

        bus.subscribe("hitl", "fast", fast_responder)
        bus.subscribe("hitl", "slow", slow_responder)

        result = await bus.publish_and_wait(
            "hitl", request_id, {"tool": "bash"}, timeout=2.0
        )

        assert result is not None
        assert result["answer"] == "fast"

    @pytest.mark.asyncio
    async def test_publish_and_wait_timeout(self):
        """publish_and_wait returns None on timeout when no one responds."""
        bus = EventBus()

        async def silent_handler(data):
            pass  # Never responds

        bus.subscribe("hitl", "silent", silent_handler)

        result = await bus.publish_and_wait(
            "hitl", "req-timeout", {"tool": "rm"}, timeout=0.1
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_error_in_subscriber_does_not_crash_others(self):
        """A failing subscriber does not prevent others from receiving."""
        bus = EventBus()
        results = []

        async def bad_handler(data):
            raise RuntimeError("I'm broken")

        async def good_handler(data):
            results.append("ok")

        bus.subscribe("ch", "bad", bad_handler)
        bus.subscribe("ch", "good", good_handler)

        await bus.publish("ch", {"test": True})

        assert results == ["ok"]
