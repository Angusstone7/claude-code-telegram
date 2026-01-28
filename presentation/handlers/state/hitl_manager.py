"""
HITL (Human-in-the-Loop) Manager

Manages permission and question state for Claude Code interactions:
- Permission requests (approve/reject)
- Question responses (AskUserQuestion tool)
- Event synchronization for async waits
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List
from datetime import datetime

from aiogram.types import Message

logger = logging.getLogger(__name__)

# Timeout constants (previously magic numbers)
PERMISSION_TIMEOUT_SECONDS = 300  # 5 minutes
QUESTION_TIMEOUT_SECONDS = 300    # 5 minutes


class HITLState(str, Enum):
    """Human-in-the-Loop interaction state"""
    IDLE = "idle"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_ANSWER = "waiting_answer"
    WAITING_PATH = "waiting_path"
    WAITING_CLARIFICATION = "waiting_clarification"


@dataclass
class PermissionContext:
    """Context for pending permission request"""
    request_id: str
    tool_name: str
    details: str
    message: Optional[Message] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuestionContext:
    """Context for pending question"""
    request_id: str
    question: str
    options: List[str]
    message: Optional[Message] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class HITLManager:
    """
    Manages Human-in-the-Loop interactions.

    Handles the async coordination between:
    1. SDK/CLI requesting permission/question
    2. Telegram UI showing buttons
    3. User responding
    4. SDK/CLI receiving response
    """

    def __init__(self):
        # Permission state
        self._permission_events: Dict[int, asyncio.Event] = {}
        self._permission_responses: Dict[int, bool] = {}
        self._permission_contexts: Dict[int, PermissionContext] = {}
        self._permission_messages: Dict[int, Message] = {}
        self._clarification_texts: Dict[int, str] = {}  # For clarification text input

        # Question state
        self._question_events: Dict[int, asyncio.Event] = {}
        self._question_responses: Dict[int, str] = {}
        self._question_contexts: Dict[int, QuestionContext] = {}
        self._question_messages: Dict[int, Message] = {}
        self._pending_options: Dict[int, List[str]] = {}

        # Input state
        self._expecting_answer: Dict[int, bool] = {}
        self._expecting_path: Dict[int, bool] = {}
        self._expecting_clarification: Dict[int, bool] = {}  # For clarification text input

        # General HITL state
        self._states: Dict[int, HITLState] = {}

    # === State Management ===

    def get_state(self, user_id: int) -> HITLState:
        """Get current HITL state for user"""
        return self._states.get(user_id, HITLState.IDLE)

    def set_state(self, user_id: int, state: HITLState) -> None:
        """Set HITL state for user"""
        self._states[user_id] = state

    def is_waiting(self, user_id: int) -> bool:
        """Check if user is in any waiting state"""
        state = self.get_state(user_id)
        return state != HITLState.IDLE

    # === Permission Handling ===

    def create_permission_event(self, user_id: int) -> asyncio.Event:
        """Create event for permission waiting"""
        event = asyncio.Event()
        self._permission_events[user_id] = event
        self.set_state(user_id, HITLState.WAITING_PERMISSION)
        return event

    def get_permission_event(self, user_id: int) -> Optional[asyncio.Event]:
        """Get existing permission event"""
        return self._permission_events.get(user_id)

    def set_permission_context(
        self,
        user_id: int,
        request_id: str,
        tool_name: str,
        details: str,
        message: Message = None
    ) -> None:
        """Set context for pending permission request"""
        self._permission_contexts[user_id] = PermissionContext(
            request_id=request_id,
            tool_name=tool_name,
            details=details,
            message=message,
        )
        if message:
            self._permission_messages[user_id] = message

    def get_permission_context(self, user_id: int) -> Optional[PermissionContext]:
        """Get pending permission context"""
        return self._permission_contexts.get(user_id)

    def get_pending_tool_name(self, user_id: int) -> Optional[str]:
        """Get tool name from pending permission context"""
        ctx = self._permission_contexts.get(user_id)
        return ctx.tool_name if ctx else None

    def get_permission_message(self, user_id: int) -> Optional[Message]:
        """Get the permission message to edit after response"""
        return self._permission_messages.get(user_id)

    async def respond_to_permission(self, user_id: int, approved: bool, clarification_text: Optional[str] = None) -> bool:
        """
        Respond to pending permission request.

        Args:
            user_id: User ID
            approved: Whether operation is approved
            clarification_text: Optional clarification text (if provided, operation will be denied with feedback)

        Returns True if response was accepted.
        """
        event = self._permission_events.get(user_id)
        if event and self.get_state(user_id) == HITLState.WAITING_PERMISSION:
            self._permission_responses[user_id] = approved
            if clarification_text:
                self._clarification_texts[user_id] = clarification_text
            event.set()
            logger.debug(f"[{user_id}] Permission response: {approved}, clarification: {bool(clarification_text)}")
            return True
        return False

    def get_permission_response(self, user_id: int) -> bool:
        """Get the permission response (after event is set)"""
        return self._permission_responses.get(user_id, False)

    def get_clarification_text(self, user_id: int) -> Optional[str]:
        """Get clarification text (if provided with permission response)"""
        return self._clarification_texts.get(user_id)

    def clear_permission_state(self, user_id: int) -> None:
        """Clear permission-related state"""
        self._permission_events.pop(user_id, None)
        self._permission_responses.pop(user_id, None)
        self._permission_contexts.pop(user_id, None)
        self._permission_messages.pop(user_id, None)
        self._clarification_texts.pop(user_id, None)
        self._expecting_clarification.pop(user_id, None)
        if self.get_state(user_id) in (HITLState.WAITING_PERMISSION, HITLState.WAITING_CLARIFICATION):
            self.set_state(user_id, HITLState.IDLE)

    # === Question Handling ===

    def create_question_event(self, user_id: int) -> asyncio.Event:
        """Create event for question waiting"""
        event = asyncio.Event()
        self._question_events[user_id] = event
        self.set_state(user_id, HITLState.WAITING_ANSWER)
        return event

    def get_question_event(self, user_id: int) -> Optional[asyncio.Event]:
        """Get existing question event"""
        return self._question_events.get(user_id)

    def set_question_context(
        self,
        user_id: int,
        request_id: str,
        question: str,
        options: List[str],
        message: Message = None
    ) -> None:
        """Set context for pending question"""
        self._question_contexts[user_id] = QuestionContext(
            request_id=request_id,
            question=question,
            options=options,
            message=message,
        )
        self._pending_options[user_id] = options
        if message:
            self._question_messages[user_id] = message

    def get_question_context(self, user_id: int) -> Optional[QuestionContext]:
        """Get pending question context"""
        return self._question_contexts.get(user_id)

    def get_question_message(self, user_id: int) -> Optional[Message]:
        """Get the question message to edit after response"""
        return self._question_messages.get(user_id)

    def get_pending_options(self, user_id: int) -> List[str]:
        """Get options for pending question"""
        return self._pending_options.get(user_id, [])

    def get_option_by_index(self, user_id: int, index: int) -> str:
        """Get option text by index"""
        options = self.get_pending_options(user_id)
        if 0 <= index < len(options):
            return options[index]
        return str(index)

    async def respond_to_question(self, user_id: int, answer: str) -> bool:
        """
        Respond to pending question.

        Returns True if response was accepted.
        """
        event = self._question_events.get(user_id)
        if event and self.get_state(user_id) == HITLState.WAITING_ANSWER:
            self._question_responses[user_id] = answer
            event.set()
            logger.debug(f"[{user_id}] Question response: {answer[:50]}...")
            return True
        return False

    def get_question_response(self, user_id: int) -> str:
        """Get the question response (after event is set)"""
        return self._question_responses.get(user_id, "")

    def clear_question_state(self, user_id: int) -> None:
        """Clear question-related state"""
        self._question_events.pop(user_id, None)
        self._question_responses.pop(user_id, None)
        self._question_contexts.pop(user_id, None)
        self._question_messages.pop(user_id, None)
        self._pending_options.pop(user_id, None)
        if self.get_state(user_id) == HITLState.WAITING_ANSWER:
            self.set_state(user_id, HITLState.IDLE)

    # === Text Input State ===

    def set_expecting_answer(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting text answer input"""
        self._expecting_answer[user_id] = expecting
        if expecting:
            self.set_state(user_id, HITLState.WAITING_ANSWER)
        elif self.get_state(user_id) == HITLState.WAITING_ANSWER:
            self.set_state(user_id, HITLState.IDLE)

    def is_expecting_answer(self, user_id: int) -> bool:
        """Check if expecting text answer"""
        return self._expecting_answer.get(user_id, False)

    def set_expecting_path(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting path input"""
        self._expecting_path[user_id] = expecting
        if expecting:
            self.set_state(user_id, HITLState.WAITING_PATH)
        elif self.get_state(user_id) == HITLState.WAITING_PATH:
            self.set_state(user_id, HITLState.IDLE)

    def is_expecting_path(self, user_id: int) -> bool:
        """Check if expecting path input"""
        return self._expecting_path.get(user_id, False)

    def set_expecting_clarification(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting clarification text input"""
        self._expecting_clarification[user_id] = expecting
        if expecting:
            self.set_state(user_id, HITLState.WAITING_CLARIFICATION)
        elif self.get_state(user_id) == HITLState.WAITING_CLARIFICATION:
            self.set_state(user_id, HITLState.IDLE)

    def is_expecting_clarification(self, user_id: int) -> bool:
        """Check if expecting clarification text"""
        return self._expecting_clarification.get(user_id, False)

    # === Cleanup ===

    def cleanup(self, user_id: int) -> None:
        """Clean up all HITL state for user"""
        self.clear_permission_state(user_id)
        self.clear_question_state(user_id)
        self._expecting_answer.pop(user_id, None)
        self._expecting_path.pop(user_id, None)
        self._expecting_clarification.pop(user_id, None)
        self._states.pop(user_id, None)

    def cancel_all_waits(self, user_id: int) -> None:
        """Cancel all waiting events (for task cancellation)"""
        # Set all events to wake up waiting coroutines
        if user_id in self._permission_events:
            self._permission_events[user_id].set()
        if user_id in self._question_events:
            self._question_events[user_id].set()
