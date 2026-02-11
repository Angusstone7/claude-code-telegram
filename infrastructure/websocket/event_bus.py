"""EventBus — async pub/sub for broadcasting events (HITL, notifications).

Supports first-response-wins pattern: multiple subscribers receive an event,
but only the first response is accepted.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Subscriber = Callable[..., Awaitable[None]]


@dataclass
class PendingRequest:
    request_id: str
    channel: str
    data: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    response_event: asyncio.Event = field(default_factory=asyncio.Event)
    response: Optional[dict[str, Any]] = None
    resolved_by: Optional[str] = None


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[tuple[str, Subscriber]]] = defaultdict(list)
        self._pending_requests: dict[str, PendingRequest] = {}

    def subscribe(self, channel: str, subscriber_id: str, callback: Subscriber) -> None:
        self._subscribers[channel].append((subscriber_id, callback))
        logger.debug(
            "EventBus: subscriber '%s' subscribed to '%s'",
            subscriber_id,
            channel,
        )

    def unsubscribe(self, channel: str, subscriber_id: str) -> None:
        self._subscribers[channel] = [
            (sid, cb) for sid, cb in self._subscribers[channel] if sid != subscriber_id
        ]
        logger.debug(
            "EventBus: subscriber '%s' unsubscribed from '%s'",
            subscriber_id,
            channel,
        )

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        subscribers = self._subscribers.get(channel, [])
        if not subscribers:
            logger.debug("EventBus: no subscribers for '%s'", channel)
            return

        logger.info(
            "EventBus: publishing to '%s' (%d subscribers)",
            channel,
            len(subscribers),
        )

        tasks = []
        for subscriber_id, callback in subscribers:
            tasks.append(self._safe_call(subscriber_id, callback, data))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_and_wait(
        self,
        channel: str,
        request_id: str,
        data: dict[str, Any],
        timeout: float = 300.0,
    ) -> Optional[dict[str, Any]]:
        """Publish event and wait for first response (first-response-wins)."""
        pending = PendingRequest(
            request_id=request_id,
            channel=channel,
            data=data,
        )
        self._pending_requests[request_id] = pending

        logger.info(
            "EventBus: publish_and_wait on '%s' request_id='%s' timeout=%.0fs",
            channel,
            request_id,
            timeout,
        )

        await self.publish(channel, {**data, "request_id": request_id})

        try:
            await asyncio.wait_for(pending.response_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "EventBus: timeout for request_id='%s' on '%s'",
                request_id,
                channel,
            )
            return None
        finally:
            self._pending_requests.pop(request_id, None)

        return pending.response

    async def respond(
        self,
        request_id: str,
        response: dict[str, Any],
        responder_id: str,
    ) -> bool:
        """Submit response for a pending request (first-response-wins)."""
        pending = self._pending_requests.get(request_id)
        if pending is None:
            logger.debug(
                "EventBus: no pending request for id='%s'",
                request_id,
            )
            return False

        if pending.response_event.is_set():
            logger.info(
                "EventBus: request '%s' already resolved by '%s', "
                "ignoring response from '%s'",
                request_id,
                pending.resolved_by,
                responder_id,
            )
            return False

        pending.response = response
        pending.resolved_by = responder_id
        pending.response_event.set()

        logger.info(
            "EventBus: request '%s' resolved by '%s'",
            request_id,
            responder_id,
        )

        # Notify all subscribers that the request has been resolved
        await self.publish(
            f"{pending.channel}_resolved",
            {
                "request_id": request_id,
                "resolved_by": responder_id,
                **response,
            },
        )

        return True

    def get_pending(self, request_id: str) -> Optional[PendingRequest]:
        return self._pending_requests.get(request_id)

    @property
    def pending_count(self) -> int:
        return len(self._pending_requests)

    async def _safe_call(
        self, subscriber_id: str, callback: Subscriber, data: dict[str, Any]
    ) -> None:
        try:
            await callback(data)
        except Exception:
            logger.exception(
                "EventBus: error in subscriber '%s'",
                subscriber_id,
            )
