"""
Plan Approval Handler

Handles plan approval workflow for Claude Code.
Extracted from MessageHandlers God Object.
"""

import logging
from typing import Optional
from aiogram.types import Message

from .base import BaseMessageHandler

logger = logging.getLogger(__name__)


class PlanApprovalHandler(BaseMessageHandler):
    """
    Handles plan approval workflow.

    Responsibilities:
    - Handle plan approval/rejection
    - Handle plan clarification input
    - Coordinate with plan manager
    - Send responses back to Claude

    Workflow:
    1. Claude sends plan → show_plan_to_user()
    2. User clicks Approve/Reject/Clarify
    3. If Clarify → handle_plan_clarification_input()
    4. Response sent back to Claude
    """

    def is_expecting_clarification(self, user_id: int) -> bool:
        """
        Check if user is expected to provide plan clarification.

        Args:
            user_id: User ID

        Returns:
            True if expecting clarification input
        """
        return self.plans.is_expecting_clarification(user_id)

    def set_expecting_clarification(self, user_id: int, expecting: bool) -> None:
        """
        Set plan clarification expectation state.

        Args:
            user_id: User ID
            expecting: True if expecting clarification
        """
        self.plans.set_expecting_clarification(user_id, expecting)
        if expecting:
            self.log_info(user_id, "Expecting plan clarification input")
        else:
            self.log_debug(user_id, "Cleared plan clarification expectation")

    async def handle_plan_clarification_input(self, message: Message) -> None:
        """
        Handle plan clarification text input from user.

        Called when user provides clarification after rejecting a plan.

        Args:
            message: Telegram message with clarification text
        """
        user_id = message.from_user.id
        clarification = message.text.strip()

        if not clarification:
            await message.answer("⚠️ Пожалуйста, введите пояснение")
            return

        self.log_info(user_id, f"Plan clarification received: {clarification[:50]}...")

        # Store clarification in plan manager
        self.plans.set_clarification_text(user_id, clarification)

        # Send response
        await message.answer(
            f"✓ Пояснение получено:\n\n{clarification[:200]}\n\n"
            "Отправляю Claude для корректировки плана..."
        )

        # Clear expectation state
        self.set_expecting_clarification(user_id, False)

        # TODO: Trigger plan re-generation with clarification
        # This should be handled by the coordinator or SDK service
        self.log_debug(user_id, "Plan clarification workflow completed")

    async def approve_plan(self, user_id: int, plan_id: str) -> bool:
        """
        Approve plan.

        Args:
            user_id: User ID
            plan_id: Plan ID

        Returns:
            True if approved successfully
        """
        self.log_info(user_id, f"Plan approved: {plan_id}")

        try:
            # Store approval in plan manager
            self.plans.approve_plan(user_id, plan_id)
            return True
        except Exception as e:
            self.log_error(user_id, f"Error approving plan: {e}")
            return False

    async def reject_plan(
        self,
        user_id: int,
        plan_id: str,
        clarification: Optional[str] = None
    ) -> bool:
        """
        Reject plan.

        Args:
            user_id: User ID
            plan_id: Plan ID
            clarification: Optional clarification text

        Returns:
            True if rejected successfully
        """
        self.log_info(user_id, f"Plan rejected: {plan_id}")

        try:
            # Store rejection in plan manager
            self.plans.reject_plan(user_id, plan_id, clarification)
            return True
        except Exception as e:
            self.log_error(user_id, f"Error rejecting plan: {e}")
            return False

    async def cancel_plan(self, user_id: int) -> None:
        """
        Cancel plan approval workflow.

        Args:
            user_id: User ID
        """
        self.log_info(user_id, "Plan workflow cancelled")
        self.plans.cancel(user_id)
        self.set_expecting_clarification(user_id, False)

    def get_pending_plan_id(self, user_id: int) -> Optional[str]:
        """
        Get ID of pending plan.

        Args:
            user_id: User ID

        Returns:
            Plan ID if exists, None otherwise
        """
        return self.plans.get_pending_plan_id(user_id)
