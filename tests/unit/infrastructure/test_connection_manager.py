"""Unit tests for ConnectionManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from infrastructure.websocket.connection_manager import ConnectionManager, WSConnection


def make_mock_websocket():
    """Create a mock WebSocket object with accept and send_json methods."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnectionManagerConnect:
    """Tests for connect() and disconnect() methods."""

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        """Test that connect() calls websocket.accept()."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        conn = await manager.connect(ws, "user1", "session1")

        ws.accept.assert_awaited_once()
        assert isinstance(conn, WSConnection)
        assert conn.user_id == "user1"
        assert conn.session_id == "session1"
        assert conn.websocket is ws

    @pytest.mark.asyncio
    async def test_connect_increments_total(self):
        """Test that connect() increments total_connections."""
        manager = ConnectionManager()
        assert manager.total_connections == 0

        ws1 = make_mock_websocket()
        await manager.connect(ws1, "user1", "s1")
        assert manager.total_connections == 1

        ws2 = make_mock_websocket()
        await manager.connect(ws2, "user1", "s2")
        assert manager.total_connections == 2

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        """Test that disconnect() removes the connection."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        conn = await manager.connect(ws, "user1", "s1")
        assert manager.total_connections == 1

        await manager.disconnect(conn)
        assert manager.total_connections == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_empty_sessions(self):
        """Test that disconnect removes empty session and user entries."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        conn = await manager.connect(ws, "user1", "s1")
        await manager.disconnect(conn)

        assert not manager.is_user_connected("user1")

    @pytest.mark.asyncio
    async def test_disconnect_keeps_other_connections(self):
        """Test that disconnecting one connection does not affect others."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()

        conn1 = await manager.connect(ws1, "user1", "s1")
        conn2 = await manager.connect(ws2, "user1", "s2")

        await manager.disconnect(conn1)

        assert manager.total_connections == 1
        assert manager.is_user_connected("user1")


class TestConnectionManagerSendToSession:
    """Tests for send_to_session() method."""

    @pytest.mark.asyncio
    async def test_send_to_session_sends_to_correct_connections(self):
        """Test that send_to_session only sends to connections in specified session."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()

        await manager.connect(ws1, "user1", "session_a")
        await manager.connect(ws2, "user1", "session_b")

        message = {"type": "update", "data": "hello"}
        sent = await manager.send_to_session("user1", "session_a", message)

        assert sent == 1
        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_to_session_multiple_connections_same_session(self):
        """Test sending to multiple connections in the same session."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()

        await manager.connect(ws1, "user1", "s1")
        await manager.connect(ws2, "user1", "s1")

        message = {"msg": "broadcast"}
        sent = await manager.send_to_session("user1", "s1", message)

        assert sent == 2
        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_send_to_session_returns_zero_for_unknown(self):
        """Test that send_to_session returns 0 for unknown user/session."""
        manager = ConnectionManager()

        sent = await manager.send_to_session("unknown", "unknown_s", {"msg": "hi"})

        assert sent == 0

    @pytest.mark.asyncio
    async def test_send_to_session_cleans_dead_connections(self):
        """Test that dead connections are cleaned up on send failure."""
        manager = ConnectionManager()

        ws_good = make_mock_websocket()
        ws_bad = make_mock_websocket()
        ws_bad.send_json = AsyncMock(side_effect=ConnectionError("Connection lost"))

        await manager.connect(ws_good, "user1", "s1")
        await manager.connect(ws_bad, "user1", "s1")
        assert manager.total_connections == 2

        message = {"msg": "test"}
        sent = await manager.send_to_session("user1", "s1", message)

        # Only the good connection should have succeeded
        assert sent == 1
        # Dead connection should have been removed
        assert manager.total_connections == 1


class TestConnectionManagerSendToUser:
    """Tests for send_to_user() method."""

    @pytest.mark.asyncio
    async def test_send_to_user_across_sessions(self):
        """Test that send_to_user sends to all sessions of a user."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        ws3 = make_mock_websocket()

        await manager.connect(ws1, "user1", "session_a")
        await manager.connect(ws2, "user1", "session_b")
        await manager.connect(ws3, "user2", "session_c")

        message = {"msg": "to_user1"}
        sent = await manager.send_to_user("user1", message)

        assert sent == 2
        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_awaited_once_with(message)
        ws3.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_to_user_unknown_returns_zero(self):
        """Test that send_to_user returns 0 for unknown user."""
        manager = ConnectionManager()

        sent = await manager.send_to_user("ghost_user", {"msg": "hi"})

        assert sent == 0


class TestConnectionManagerBroadcast:
    """Tests for broadcast() method."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        """Test that broadcast sends to all connected clients."""
        manager = ConnectionManager()
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        ws3 = make_mock_websocket()

        await manager.connect(ws1, "user1", "s1")
        await manager.connect(ws2, "user2", "s2")
        await manager.connect(ws3, "user3", "s3")

        message = {"type": "broadcast", "text": "hello all"}
        sent = await manager.broadcast(message)

        assert sent == 3
        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_awaited_once_with(message)
        ws3.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_empty_returns_zero(self):
        """Test that broadcast returns 0 when no connections exist."""
        manager = ConnectionManager()

        sent = await manager.broadcast({"msg": "nobody"})

        assert sent == 0


class TestConnectionManagerProperties:
    """Tests for is_user_connected, total_connections, connected_users."""

    @pytest.mark.asyncio
    async def test_is_user_connected_true(self):
        """Test is_user_connected returns True for connected user."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        await manager.connect(ws, "user1", "s1")

        assert manager.is_user_connected("user1") is True

    @pytest.mark.asyncio
    async def test_is_user_connected_false(self):
        """Test is_user_connected returns False for unknown user."""
        manager = ConnectionManager()

        assert manager.is_user_connected("unknown") is False

    @pytest.mark.asyncio
    async def test_is_user_connected_after_disconnect(self):
        """Test is_user_connected returns False after all user connections disconnected."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        conn = await manager.connect(ws, "user1", "s1")
        await manager.disconnect(conn)

        assert manager.is_user_connected("user1") is False

    @pytest.mark.asyncio
    async def test_total_connections_counts_all(self):
        """Test total_connections counts across users and sessions."""
        manager = ConnectionManager()

        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        ws3 = make_mock_websocket()

        await manager.connect(ws1, "user1", "s1")
        await manager.connect(ws2, "user1", "s2")
        await manager.connect(ws3, "user2", "s1")

        assert manager.total_connections == 3

    @pytest.mark.asyncio
    async def test_connected_users_lists_all(self):
        """Test connected_users returns list of all connected user IDs."""
        manager = ConnectionManager()

        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()

        await manager.connect(ws1, "alice", "s1")
        await manager.connect(ws2, "bob", "s1")

        users = manager.connected_users
        assert set(users) == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_connected_users_empty(self):
        """Test connected_users returns empty list when no connections."""
        manager = ConnectionManager()

        assert manager.connected_users == []

    @pytest.mark.asyncio
    async def test_connected_users_after_full_disconnect(self):
        """Test connected_users excludes fully disconnected users."""
        manager = ConnectionManager()
        ws = make_mock_websocket()

        conn = await manager.connect(ws, "user1", "s1")
        await manager.disconnect(conn)

        assert "user1" not in manager.connected_users


class TestConnectionManagerDeadConnectionCleanup:
    """Tests for automatic dead connection cleanup."""

    @pytest.mark.asyncio
    async def test_dead_connection_removed_on_send_to_user(self):
        """Test that dead connections are cleaned up during send_to_user."""
        manager = ConnectionManager()

        ws_dead = make_mock_websocket()
        ws_dead.send_json = AsyncMock(side_effect=Exception("Connection dead"))

        await manager.connect(ws_dead, "user1", "s1")
        assert manager.total_connections == 1

        sent = await manager.send_to_user("user1", {"msg": "test"})

        assert sent == 0
        assert manager.total_connections == 0

    @pytest.mark.asyncio
    async def test_dead_connection_removed_on_broadcast(self):
        """Test that dead connections are cleaned up during broadcast."""
        manager = ConnectionManager()

        ws_good = make_mock_websocket()
        ws_dead = make_mock_websocket()
        ws_dead.send_json = AsyncMock(side_effect=RuntimeError("broken pipe"))

        await manager.connect(ws_good, "user1", "s1")
        await manager.connect(ws_dead, "user2", "s2")
        assert manager.total_connections == 2

        sent = await manager.broadcast({"msg": "all"})

        assert sent == 1
        assert manager.total_connections == 1
        assert manager.is_user_connected("user1") is True
        assert manager.is_user_connected("user2") is False
