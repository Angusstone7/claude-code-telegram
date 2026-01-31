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


@dataclass
class HITLUserState:
    """
    Consolidated HITL state for a single user.

    Replaces 12+ separate dictionaries with a single state object
    to prevent race conditions from non-atomic multi-dict operations.
    """
    # Permission state
    permission_event: Optional[asyncio.Event] = None
    permission_response: Optional[bool] = None
    permission_context: Optional[PermissionContext] = None
    permission_message: Optional[Message] = None
    clarification_text: Optional[str] = None

    # Question state
    question_event: Optional[asyncio.Event] = None
    question_response: Optional[str] = None
    question_context: Optional[QuestionContext] = None
    question_message: Optional[Message] = None
    pending_options: Optional[List[str]] = None

    # Input expectations
    expecting_answer: bool = False
    expecting_path: bool = False
    expecting_clarification: bool = False

    # General state
    state: HITLState = HITLState.IDLE


class HITLManager:
    """
    Manages Human-in-the-Loop interactions with thread-safe operations.

    Handles the async coordination between:
    1. SDK/CLI requesting permission/question
    2. Telegram UI showing buttons
    3. User responding
    4. SDK/CLI receiving response

    Thread-safety: Uses asyncio.Lock to ensure atomic updates to user state.
    """

    def __init__(self):
        # Single consolidated state dictionary per user
        self._user_states: Dict[int, HITLUserState] = {}
        # Lock for atomic state updates
        self._lock = asyncio.Lock()

    # === Helper Methods ===

    def _get_or_create_state(self, user_id: int) -> HITLUserState:
        """Get or create user state (internal helper)"""
        if user_id not in self._user_states:
            self._user_states[user_id] = HITLUserState()
        return self._user_states[user_id]

    # === State Management ===

    def get_state(self, user_id: int) -> HITLState:
        """Get current HITL state for user"""
        state = self._user_states.get(user_id)
        return state.state if state else HITLState.IDLE

    def set_state(self, user_id: int, new_state: HITLState) -> None:
        """Set HITL state for user"""
        user_state = self._get_or_create_state(user_id)
        user_state.state = new_state

    def is_waiting(self, user_id: int) -> bool:
        """Check if user is in any waiting state"""
        state = self.get_state(user_id)
        return state != HITLState.IDLE

    # === Permission Handling ===

    def create_permission_event(self, user_id: int) -> asyncio.Event:
        """Create event for permission waiting"""
        event = asyncio.Event()
        user_state = self._get_or_create_state(user_id)
        user_state.permission_event = event
        user_state.state = HITLState.WAITING_PERMISSION
        return event

    def get_permission_event(self, user_id: int) -> Optional[asyncio.Event]:
        """Get existing permission event"""
        user_state = self._user_states.get(user_id)
        return user_state.permission_event if user_state else None

    def set_permission_context(
        self,
        user_id: int,
        request_id: str,
        tool_name: str,
        details: str,
        message: Message = None
    ) -> None:
        """Set context for pending permission request"""
        user_state = self._get_or_create_state(user_id)
        user_state.permission_context = PermissionContext(
            request_id=request_id,
            tool_name=tool_name,
            details=details,
            message=message,
        )
        if message:
            user_state.permission_message = message

    def get_permission_context(self, user_id: int) -> Optional[PermissionContext]:
        """Get pending permission context"""
        user_state = self._user_states.get(user_id)
        return user_state.permission_context if user_state else None

    def get_pending_tool_name(self, user_id: int) -> Optional[str]:
        """Get tool name from pending permission context"""
        user_state = self._user_states.get(user_id)
        ctx = user_state.permission_context if user_state else None
        return ctx.tool_name if ctx else None

    def get_permission_message(self, user_id: int) -> Optional[Message]:
        """Get the permission message to edit after response"""
        user_state = self._user_states.get(user_id)
        return user_state.permission_message if user_state else None

    async def respond_to_permission(self, user_id: int, approved: bool, clarification_text: Optional[str] = None) -> bool:
        """
        Respond to pending permission request.

        Args:
            user_id: User ID
            approved: Whether operation is approved
            clarification_text: Optional clarification text (if provided, operation will be denied with feedback)

        Returns True if response was accepted.

        Thread-safety: Uses lock to ensure atomic state update.
        """
        async with self._lock:
            user_state = self._user_states.get(user_id)
            if user_state and user_state.permission_event and user_state.state == HITLState.WAITING_PERMISSION:
                # Atomic update - all fields updated together
                user_state.permission_response = approved
                if clarification_text:
                    user_state.clarification_text = clarification_text
                user_state.permission_event.set()
                logger.debug(f"[{user_id}] Permission response: {approved}, clarification: {bool(clarification_text)}")
                return True
            return False

    def get_permission_response(self, user_id: int) -> bool:
        """Get the permission response (after event is set)"""
        user_state = self._user_states.get(user_id)
        return user_state.permission_response if (user_state and user_state.permission_response is not None) else False

    def get_clarification_text(self, user_id: int) -> Optional[str]:
        """Get clarification text (if provided with permission response)"""
        user_state = self._user_states.get(user_id)
        return user_state.clarification_text if user_state else None

    def clear_permission_state(self, user_id: int) -> None:
        """Clear permission-related state"""
        user_state = self._user_states.get(user_id)
        if user_state:
            # Clear all permission-related fields
            user_state.permission_event = None
            user_state.permission_response = None
            user_state.permission_context = None
            user_state.permission_message = None
            user_state.clarification_text = None
            user_state.expecting_clarification = False
            if user_state.state in (HITLState.WAITING_PERMISSION, HITLState.WAITING_CLARIFICATION):
                user_state.state = HITLState.IDLE

    # === Question Handling ===

    def create_question_event(self, user_id: int) -> asyncio.Event:
        """Create event for question waiting"""
        event = asyncio.Event()
        user_state = self._get_or_create_state(user_id)
        user_state.question_event = event
        user_state.state = HITLState.WAITING_ANSWER
        return event

    def get_question_event(self, user_id: int) -> Optional[asyncio.Event]:
        """Get existing question event"""
        user_state = self._user_states.get(user_id)
        return user_state.question_event if user_state else None

    def set_question_context(
        self,
        user_id: int,
        request_id: str,
        question: str,
        options: List[str],
        message: Message = None
    ) -> None:
        """Set context for pending question"""
        user_state = self._get_or_create_state(user_id)
        user_state.question_context = QuestionContext(
            request_id=request_id,
            question=question,
            options=options,
            message=message,
        )
        user_state.pending_options = options
        if message:
            user_state.question_message = message

    def get_question_context(self, user_id: int) -> Optional[QuestionContext]:
        """Get pending question context"""
        user_state = self._user_states.get(user_id)
        return user_state.question_context if user_state else None

    def get_question_message(self, user_id: int) -> Optional[Message]:
        """Get the question message to edit after response"""
        user_state = self._user_states.get(user_id)
        return user_state.question_message if user_state else None

    def get_pending_options(self, user_id: int) -> List[str]:
        """Get options for pending question"""
        user_state = self._user_states.get(user_id)
        return user_state.pending_options if (user_state and user_state.pending_options) else []

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

        Thread-safety: Uses lock to ensure atomic state update.
        """
        async with self._lock:
            user_state = self._user_states.get(user_id)
            if user_state and user_state.question_event and user_state.state == HITLState.WAITING_ANSWER:
                # Atomic update
                user_state.question_response = answer
                user_state.question_event.set()
                logger.debug(f"[{user_id}] Question response: {answer[:50]}...")
                return True
            return False

    def get_question_response(self, user_id: int) -> str:
        """Get the question response (after event is set)"""
        user_state = self._user_states.get(user_id)
        return user_state.question_response if (user_state and user_state.question_response) else ""

    def clear_question_state(self, user_id: int) -> None:
        """Clear question-related state"""
        user_state = self._user_states.get(user_id)
        if user_state:
            # Clear all question-related fields
            user_state.question_event = None
            user_state.question_response = None
            user_state.question_context = None
            user_state.question_message = None
            user_state.pending_options = None
            if user_state.state == HITLState.WAITING_ANSWER:
                user_state.state = HITLState.IDLE

    # === Text Input State ===

    def set_expecting_answer(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting text answer input"""
        user_state = self._get_or_create_state(user_id)
        user_state.expecting_answer = expecting
        if expecting:
            user_state.state = HITLState.WAITING_ANSWER
        elif user_state.state == HITLState.WAITING_ANSWER:
            user_state.state = HITLState.IDLE

    def is_expecting_answer(self, user_id: int) -> bool:
        """Check if expecting text answer"""
        user_state = self._user_states.get(user_id)
        return user_state.expecting_answer if user_state else False

    def set_expecting_path(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting path input"""
        user_state = self._get_or_create_state(user_id)
        user_state.expecting_path = expecting
        if expecting:
            user_state.state = HITLState.WAITING_PATH
        elif user_state.state == HITLState.WAITING_PATH:
            user_state.state = HITLState.IDLE

    def is_expecting_path(self, user_id: int) -> bool:
        """Check if expecting path input"""
        user_state = self._user_states.get(user_id)
        return user_state.expecting_path if user_state else False

    def set_expecting_clarification(self, user_id: int, expecting: bool) -> None:
        """Set whether expecting clarification text input"""
        user_state = self._get_or_create_state(user_id)
        user_state.expecting_clarification = expecting
        if expecting:
            user_state.state = HITLState.WAITING_CLARIFICATION
        elif user_state.state == HITLState.WAITING_CLARIFICATION:
            user_state.state = HITLState.IDLE

    def is_expecting_clarification(self, user_id: int) -> bool:
        """Check if expecting clarification text"""
        user_state = self._user_states.get(user_id)
        return user_state.expecting_clarification if user_state else False

    # === Cleanup ===

    def cleanup(self, user_id: int) -> None:
        """Clean up all HITL state for user"""
        self.clear_permission_state(user_id)
        self.clear_question_state(user_id)
        user_state = self._user_states.get(user_id)
        if user_state:
            user_state.expecting_answer = False
            user_state.expecting_path = False
            user_state.expecting_clarification = False
            user_state.state = HITLState.IDLE

    def cancel_all_waits(self, user_id: int) -> None:
        """Cancel all waiting events (for task cancellation)"""
        # Set all events to wake up waiting coroutines
        user_state = self._user_states.get(user_id)
        if user_state:
            if user_state.permission_event:
                user_state.permission_event.set()
            if user_state.question_event:
                user_state.question_event.set()
