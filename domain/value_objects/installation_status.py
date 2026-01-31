"""
Installation Status Value Object

Replaces tuple[bool, str] return from check_claude_installed()
with a proper value object (fixes Primitive Obsession).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class InstallationStatus:
    """
    Value object representing installation status of a component.

    Replaces tuple[bool, str] with semantic methods and immutable data.
    """
    is_installed: bool
    message: str
    version: str = ""

    @classmethod
    def installed(cls, version: str) -> "InstallationStatus":
        """Create status for installed component"""
        return cls(
            is_installed=True,
            message=f"Installed: {version}",
            version=version,
        )

    @classmethod
    def not_installed(cls, error: str) -> "InstallationStatus":
        """Create status for component with installation error"""
        return cls(
            is_installed=False,
            message=f"Error: {error}",
        )

    @classmethod
    def not_found(cls) -> "InstallationStatus":
        """Create status for component not found"""
        return cls(
            is_installed=False,
            message="Not found. Install with: npm install -g @anthropic-ai/claude-code",
        )

    def __bool__(self) -> bool:
        """Allow using status in boolean context"""
        return self.is_installed

    def __str__(self) -> str:
        return self.message
