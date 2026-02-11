"""ConnectionManager — per-user, per-session WebSocket connection management."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    websocket: WebSocket
    user_id: str
    session_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: Optional[datetime] = None


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> session_id -> list[WSConnection]
        self._connections: dict[str, dict[str, list[WSConnection]]] = defaultdict(
            lambda: defaultdict(list)
        )

    async def connect(
        self, websocket: WebSocket, user_id: str, session_id: str
    ) -> WSConnection:
        await websocket.accept()
        conn = WSConnection(
            websocket=websocket,
            user_id=user_id,
            session_id=session_id,
        )
        self._connections[user_id][session_id].append(conn)
        logger.info(
            "WS connected: user='%s' session='%s' (total=%d)",
            user_id,
            session_id,
            self.total_connections,
        )
        return conn

    async def disconnect(self, conn: WSConnection) -> None:
        user_conns = self._connections.get(conn.user_id, {})
        session_conns = user_conns.get(conn.session_id, [])
        if conn in session_conns:
            session_conns.remove(conn)
            if not session_conns:
                user_conns.pop(conn.session_id, None)
            if not user_conns:
                self._connections.pop(conn.user_id, None)

        logger.info(
            "WS disconnected: user='%s' session='%s' (total=%d)",
            conn.user_id,
            conn.session_id,
            self.total_connections,
        )

    async def send_to_session(
        self, user_id: str, session_id: str, message: dict[str, Any]
    ) -> int:
        """Send message to all connections of a user in a specific session."""
        connections = self._connections.get(user_id, {}).get(session_id, [])
        sent = 0
        dead: list[WSConnection] = []

        for conn in connections:
            try:
                await conn.websocket.send_json(message)
                sent += 1
            except Exception:
                logger.warning(
                    "WS send failed: user='%s' session='%s'",
                    user_id,
                    session_id,
                )
                dead.append(conn)

        for conn in dead:
            await self.disconnect(conn)

        return sent

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> int:
        """Send message to all connections of a user across all sessions."""
        user_conns = self._connections.get(user_id, {})
        sent = 0
        for session_id in list(user_conns.keys()):
            sent += await self.send_to_session(user_id, session_id, message)
        return sent

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Send message to all connected clients."""
        sent = 0
        for user_id in list(self._connections.keys()):
            sent += await self.send_to_user(user_id, message)
        return sent

    def get_user_connections(self, user_id: str) -> list[WSConnection]:
        result: list[WSConnection] = []
        for conns in self._connections.get(user_id, {}).values():
            result.extend(conns)
        return result

    def get_session_connections(
        self, user_id: str, session_id: str
    ) -> list[WSConnection]:
        return list(self._connections.get(user_id, {}).get(session_id, []))

    def is_user_connected(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def update_ping(self, conn: WSConnection) -> None:
        conn.last_ping = datetime.utcnow()

    @property
    def total_connections(self) -> int:
        total = 0
        for sessions in self._connections.values():
            for conns in sessions.values():
                total += len(conns)
        return total

    @property
    def connected_users(self) -> list[str]:
        return list(self._connections.keys())
