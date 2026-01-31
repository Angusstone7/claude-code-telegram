"""
Plan Approval Manager

Manages plan approval state for ExitPlanMode tool:
- Storing pending plan content
- Handling approval/rejection/clarification responses
- Event synchronization
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict
from datetime import datetime

from aiogram.types import Message

logger = logging.getLogger(__name__)

# Timeout for plan approval
PLAN_APPROVAL_TIMEOUT_SECONDS = 600  # 10 minutes


class PlanResponse(str, Enum):
    """Types of plan responses"""
    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"
    CLARIFY = "clarify"  # Prefix with :text


@dataclass
class PlanContext:
    """Context for pending plan approval"""
    request_id: str
    plan_file: str
    plan_content: Optional[str] = None
    message: Optional[Message] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class PlanApprovalManager:
    """
    Manages ExitPlanMode (plan approval) interactions.

    Handles the async coordination for:
    1. Claude presenting a plan for approval
    2. Telegram UI showing the plan with buttons
    3. User approving/rejecting/requesting clarification
    4. Claude receiving the response
    """

    def __init__(self):
        self._events: Dict[int, asyncio.Event] = {}
        self._responses: Dict[int, str] = {}
        self._contexts: Dict[int, PlanContext] = {}
        self._messages: Dict[int, Message] = {}
        self._expecting_clarification: Dict[int, bool] = {}

    # === State Queries ===

    def is_waiting_approval(self, user_id: int) -> bool:
        """Check if waiting for plan approval"""
        return user_id in self._events and not self._events[user_id].is_set()

    def is_expecting_clarification(self, user_id: int) -> bool:
        """Check if expecting clarification text input"""
        return self._expecting_clarification.get(user_id, False)

    def get_context(self, user_id: int) -> Optional[PlanContext]:
        """Get pending plan context"""
        return self._contexts.get(user_id)

    def get_message(self, user_id: int) -> Optional[Message]:
        """Get the plan message to edit after response"""
        return self._messages.get(user_id)

    # === Event Management ===

    def create_event(self, user_id: int) -> asyncio.Event:
        """Create event for plan approval waiting"""
        event = asyncio.Event()
        self._events[user_id] = event
        return event

    def get_event(self, user_id: int) -> Optional[asyncio.Event]:
        """Get existing plan event"""
        return self._events.get(user_id)

    # === Context Management ===

    def set_context(
        self,
        user_id: int,
        request_id: str,
        plan_file: str,
        plan_content: str = None,
        message: Message = None
    ) -> None:
        """Set context for pending plan approval"""
        self._contexts[user_id] = PlanContext(
            request_id=request_id,
            plan_file=plan_file,
            plan_content=plan_content,
            message=message,
        )
        if message:
            self._messages[user_id] = message

    def set_expecting_clarification(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting clarification text"""
        self._expecting_clarification[user_id] = expecting

    # === Response Handling ===

    async def respond(self, user_id: int, response: str) -> bool:
        """
        Respond to pending plan approval.

        Args:
            user_id: User ID
            response: One of "approve", "reject", "cancel", or "clarify:text"

        Returns:
            True if response was accepted
        """
        event = self._events.get(user_id)
        if event:
            self._responses[user_id] = response
            self._expecting_clarification.pop(user_id, None)
            event.set()
            logger.info(f"[{user_id}] Plan response: {response[:50]}...")
            return True
        return False

    async def respond_approve(self, user_id: int) -> bool:
        """Approve the plan"""
        return await self.respond(user_id, PlanResponse.APPROVE.value)

    async def respond_reject(self, user_id: int) -> bool:
        """Reject the plan"""
        return await self.respond(user_id, PlanResponse.REJECT.value)

    async def respond_cancel(self, user_id: int) -> bool:
        """Cancel the plan (and task)"""
        return await self.respond(user_id, PlanResponse.CANCEL.value)

    async def respond_clarify(self, user_id: int, clarification: str) -> bool:
        """Request plan clarification"""
        return await self.respond(user_id, f"{PlanResponse.CLARIFY.value}:{clarification}")

    def get_response(self, user_id: int) -> str:
        """Get the plan response (after event is set)"""
        return self._responses.get(user_id, PlanResponse.REJECT.value)

    # === Cleanup ===

    def cleanup(self, user_id: int) -> None:
        """Clean up all plan state for user"""
        self._events.pop(user_id, None)
        self._responses.pop(user_id, None)
        self._contexts.pop(user_id, None)
        self._messages.pop(user_id, None)
        self._expecting_clarification.pop(user_id, None)

    def cancel_wait(self, user_id: int) -> None:
        """Cancel waiting event (for task cancellation)"""
        if user_id in self._events:
            self._events[user_id].set()
