"""
Variable Validation Service

Domain service for validating context variables.
Moved from presentation layer to follow DDD principles.

Business rules for variable names:
- Must start with uppercase letter
- Can only contain uppercase letters, digits, underscore
- Reserved names are not allowed
"""

import re
from dataclasses import dataclass
from typing import Optional, Set


# Reserved variable names that cannot be used
RESERVED_NAMES: Set[str] = {
    "PATH", "HOME", "USER", "PWD", "SHELL",
    "TERM", "LANG", "LC_ALL", "EDITOR",
    "ANTHROPIC_API_KEY", "TELEGRAM_TOKEN",
    "DATABASE_URL", "SECRET_KEY",
}

# Maximum lengths
MAX_VAR_NAME_LENGTH = 64
MAX_VAR_VALUE_LENGTH = 10_000
MAX_VAR_DESC_LENGTH = 500


@dataclass(frozen=True)
class ValidationResult:
    """Result of variable validation"""
    is_valid: bool
    error: Optional[str] = None
    normalized_value: Optional[str] = None

    @classmethod
    def valid(cls, normalized: str = None) -> "ValidationResult":
        return cls(is_valid=True, normalized_value=normalized)

    @classmethod
    def invalid(cls, error: str) -> "ValidationResult":
        return cls(is_valid=False, error=error)


class VariableValidationService:
    """
    Domain service for variable validation.

    Contains all business rules for context variables.
    """

    # Pattern: starts with uppercase letter, only A-Z, 0-9, _
    NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')

    def validate_name(self, name: str) -> ValidationResult:
        """
        Validate variable name according to domain rules.

        Business rules:
        1. Must not be empty
        2. Must start with uppercase letter
        3. Can only contain uppercase letters, digits, underscore
        4. Must not be a reserved name
        5. Must not exceed max length

        Args:
            name: Variable name to validate

        Returns:
            ValidationResult with normalized name if valid
        """
        # Normalize to uppercase and strip
        normalized = name.strip().upper()

        if not normalized:
            return ValidationResult.invalid("Имя переменной не может быть пустым")

        if len(normalized) > MAX_VAR_NAME_LENGTH:
            return ValidationResult.invalid(
                f"Имя переменной не должно превышать {MAX_VAR_NAME_LENGTH} символов"
            )

        if not self.NAME_PATTERN.match(normalized):
            return ValidationResult.invalid(
                "Имя переменной должно:\n"
                "• Начинаться с буквы (A-Z)\n"
                "• Содержать только буквы, цифры и _\n\n"
                "Например: GITLAB_TOKEN, API_KEY, PROJECT_STACK"
            )

        if normalized in RESERVED_NAMES:
            return ValidationResult.invalid(
                f"'{normalized}' является зарезервированным именем.\n"
                f"Выберите другое имя."
            )

        return ValidationResult.valid(normalized)

    def validate_value(self, value: str) -> ValidationResult:
        """
        Validate variable value.

        Business rules:
        1. Must not be empty
        2. Must not exceed max length
        3. Must not contain null bytes

        Args:
            value: Variable value to validate

        Returns:
            ValidationResult with stripped value if valid
        """
        stripped = value.strip()

        if not stripped:
            return ValidationResult.invalid("Значение переменной не может быть пустым")

        if len(stripped) > MAX_VAR_VALUE_LENGTH:
            return ValidationResult.invalid(
                f"Значение не должно превышать {MAX_VAR_VALUE_LENGTH} символов"
            )

        if "\x00" in stripped:
            return ValidationResult.invalid("Значение содержит недопустимые символы")

        return ValidationResult.valid(stripped)

    def validate_description(self, description: str) -> ValidationResult:
        """
        Validate variable description.

        Business rules:
        1. Can be empty (optional)
        2. Must not exceed max length

        Args:
            description: Variable description to validate

        Returns:
            ValidationResult with stripped description
        """
        stripped = description.strip() if description else ""

        if len(stripped) > MAX_VAR_DESC_LENGTH:
            return ValidationResult.invalid(
                f"Описание не должно превышать {MAX_VAR_DESC_LENGTH} символов"
            )

        return ValidationResult.valid(stripped)

    def validate_all(
        self,
        name: str,
        value: str,
        description: str = ""
    ) -> ValidationResult:
        """
        Validate all variable fields at once.

        Args:
            name: Variable name
            value: Variable value
            description: Variable description (optional)

        Returns:
            ValidationResult (first error found or valid)
        """
        name_result = self.validate_name(name)
        if not name_result.is_valid:
            return name_result

        value_result = self.validate_value(value)
        if not value_result.is_valid:
            return value_result

        desc_result = self.validate_description(description)
        if not desc_result.is_valid:
            return desc_result

        return ValidationResult.valid()


# Singleton instance for convenience
_service: Optional[VariableValidationService] = None


def get_variable_validation_service() -> VariableValidationService:
    """Get singleton instance of VariableValidationService"""
    global _service
    if _service is None:
        _service = VariableValidationService()
    return _service
