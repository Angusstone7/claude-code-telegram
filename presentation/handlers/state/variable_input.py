"""
Variable Input Manager

State machine for the 3-step variable input flow:
1. Name input (validated)
2. Value input
3. Description input (optional)

Separates the variable input flow logic from MessageHandlers.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Tuple
from datetime import datetime

from aiogram.types import Message

logger = logging.getLogger(__name__)


class VariableInputStep(str, Enum):
    """Current step in variable input flow"""
    IDLE = "idle"
    EXPECTING_NAME = "expecting_name"
    EXPECTING_VALUE = "expecting_value"
    EXPECTING_DESCRIPTION = "expecting_description"


@dataclass
class VariableInputContext:
    """Context for variable input flow"""
    step: VariableInputStep = VariableInputStep.IDLE
    var_name: Optional[str] = None
    var_value: Optional[str] = None
    menu_message: Optional[Message] = None
    is_editing: bool = False  # True if editing existing variable
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ValidationResult:
    """Result of variable name validation"""
    is_valid: bool
    error: Optional[str] = None
    normalized_name: Optional[str] = None

    @classmethod
    def valid(cls, name: str) -> "ValidationResult":
        return cls(is_valid=True, normalized_name=name)

    @classmethod
    def invalid(cls, error: str) -> "ValidationResult":
        return cls(is_valid=False, error=error)


class VariableInputManager:
    """
    Manages variable input state machine.

    Extracted from MessageHandlers to follow Single Responsibility Principle.
    Handles the multi-step flow of adding/editing context variables.
    """

    # Validation pattern: uppercase letters, numbers, underscore, starts with letter
    NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')

    def __init__(self):
        self._contexts: Dict[int, VariableInputContext] = {}

    # === State Queries ===

    def get_context(self, user_id: int) -> VariableInputContext:
        """Get or create input context for user"""
        if user_id not in self._contexts:
            self._contexts[user_id] = VariableInputContext()
        return self._contexts[user_id]

    def get_step(self, user_id: int) -> VariableInputStep:
        """Get current step for user"""
        return self.get_context(user_id).step

    def is_active(self, user_id: int) -> bool:
        """Check if user is in variable input flow"""
        return self.get_step(user_id) != VariableInputStep.IDLE

    def is_expecting_name(self, user_id: int) -> bool:
        """Check if expecting variable name input"""
        return self.get_step(user_id) == VariableInputStep.EXPECTING_NAME

    def is_expecting_value(self, user_id: int) -> bool:
        """Check if expecting variable value input"""
        return self.get_step(user_id) == VariableInputStep.EXPECTING_VALUE

    def is_expecting_description(self, user_id: int) -> bool:
        """Check if expecting variable description input"""
        return self.get_step(user_id) == VariableInputStep.EXPECTING_DESCRIPTION

    # === State Transitions ===

    def start_add_flow(self, user_id: int, menu_message: Message = None) -> None:
        """Start new variable add flow - expect name first"""
        self._contexts[user_id] = VariableInputContext(
            step=VariableInputStep.EXPECTING_NAME,
            menu_message=menu_message,
            is_editing=False,
        )
        logger.debug(f"[{user_id}] Started variable add flow")

    def start_edit_flow(
        self,
        user_id: int,
        var_name: str,
        menu_message: Message = None
    ) -> None:
        """Start variable edit flow - expect new value"""
        self._contexts[user_id] = VariableInputContext(
            step=VariableInputStep.EXPECTING_VALUE,
            var_name=var_name,
            menu_message=menu_message,
            is_editing=True,
        )
        logger.debug(f"[{user_id}] Started variable edit flow for {var_name}")

    def move_to_value_step(self, user_id: int, var_name: str) -> None:
        """Move to value input step"""
        ctx = self.get_context(user_id)
        ctx.step = VariableInputStep.EXPECTING_VALUE
        ctx.var_name = var_name
        logger.debug(f"[{user_id}] Moved to value step for {var_name}")

    def move_to_description_step(self, user_id: int, var_value: str) -> None:
        """Move to description input step"""
        ctx = self.get_context(user_id)
        ctx.step = VariableInputStep.EXPECTING_DESCRIPTION
        ctx.var_value = var_value
        logger.debug(f"[{user_id}] Moved to description step")

    def cancel(self, user_id: int) -> None:
        """Cancel variable input flow"""
        self._contexts.pop(user_id, None)
        logger.debug(f"[{user_id}] Variable input cancelled")

    def complete(self, user_id: int) -> None:
        """Complete variable input flow"""
        self._contexts.pop(user_id, None)
        logger.debug(f"[{user_id}] Variable input completed")

    # === Accessors ===

    def get_var_name(self, user_id: int) -> Optional[str]:
        """Get variable name being input"""
        return self.get_context(user_id).var_name

    def get_var_value(self, user_id: int) -> Optional[str]:
        """Get variable value being input"""
        return self.get_context(user_id).var_value

    def get_var_data(self, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        """Get (var_name, var_value) tuple"""
        ctx = self.get_context(user_id)
        return (ctx.var_name, ctx.var_value)

    def get_menu_message(self, user_id: int) -> Optional[Message]:
        """Get the menu message to update"""
        return self.get_context(user_id).menu_message

    def is_editing(self, user_id: int) -> bool:
        """Check if editing existing variable"""
        return self.get_context(user_id).is_editing

    # === Validation (Business Logic - should be in domain) ===

    def validate_name(self, name: str) -> ValidationResult:
        """
        Validate variable name.

        Business rules:
        - Must start with uppercase letter
        - Can only contain uppercase letters, digits, underscore
        - Auto-converts to uppercase

        NOTE: This validation logic should ideally be in domain layer
        (domain/services/variable_validation_service.py).
        Keeping here temporarily for refactoring step-by-step.
        """
        # Normalize to uppercase
        normalized = name.strip().upper()

        if not normalized:
            return ValidationResult.invalid("Имя не может быть пустым")

        if not self.NAME_PATTERN.match(normalized):
            return ValidationResult.invalid(
                "Имя должно:\n"
                "• Начинаться с буквы\n"
                "• Содержать только буквы, цифры и _\n\n"
                "Например: GITLAB_TOKEN, API_KEY, PROJECT_STACK"
            )

        return ValidationResult.valid(normalized)

    def validate_value(self, value: str) -> ValidationResult:
        """Validate variable value"""
        if not value or not value.strip():
            return ValidationResult.invalid("Значение не может быть пустым")
        return ValidationResult.valid(value.strip())
