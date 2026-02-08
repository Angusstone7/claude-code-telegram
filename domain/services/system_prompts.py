"""System prompts for AI service

Domain-level prompts define the behavior and personality of the AI assistant.
Prompts are loaded from /prompts/*.txt files at runtime, with hardcoded fallbacks.
This follows the Open/Closed Principle — add new prompt files without modifying code.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Directory containing prompt files (relative to project root)
_PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", "prompts"))


def _load_prompt(name: str, fallback: str) -> str:
    """Load prompt from file, fall back to hardcoded string."""
    path = _PROMPTS_DIR / f"{name}.txt"
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
    except Exception as e:
        logger.warning(f"Failed to load prompt {path}: {e}")
    return fallback


# Hardcoded fallbacks (used if prompt files are missing)
_FALLBACK_DEVOPS = """\
You are an intelligent DevOps assistant with access to a Linux server via SSH.
You can help with:
- Server administration and troubleshooting
- Docker container management
- Git operations and CI/CD pipelines
- Log analysis and monitoring
- System resource monitoring

When executing commands:
1. Always explain what the command does before suggesting it
2. For dangerous operations (rm -rf, formatting, etc.), always ask for confirmation
3. Provide clear explanations of command output
4. Suggest safer alternatives when possible

You have access to bash command execution tool. Use it to help the user."""

_FALLBACK_CODE_ASSISTANT = """\
You are an expert programmer and code assistant.
You can help with:
- Writing and reviewing code
- Debugging and troubleshooting
- Code optimization and refactoring
- Explaining code and concepts

Provide clear, concise explanations and well-structured code examples."""

_FALLBACK_SECURITY_AUDITOR = """\
You are a security specialist focused on identifying and explaining security issues.
When analyzing systems or code:
1. Identify potential vulnerabilities
2. Explain the risks clearly
3. Suggest remediation steps
4. Prioritize issues by severity"""


class SystemPrompts:
    """Predefined system prompts for different use cases.

    Prompts are loaded from prompts/*.txt files.
    If a file is missing, the hardcoded fallback is used.
    To add a new role: create prompts/{role}.txt and add mapping in for_role().
    """

    DEVOPS = _load_prompt("devops", _FALLBACK_DEVOPS)
    CODE_ASSISTANT = _load_prompt("code_assistant", _FALLBACK_CODE_ASSISTANT)
    SECURITY_AUDITOR = _load_prompt("security_auditor", _FALLBACK_SECURITY_AUDITOR)

    @classmethod
    def reload(cls) -> None:
        """Reload all prompts from disk (hot-reload support)."""
        cls.DEVOPS = _load_prompt("devops", _FALLBACK_DEVOPS)
        cls.CODE_ASSISTANT = _load_prompt("code_assistant", _FALLBACK_CODE_ASSISTANT)
        cls.SECURITY_AUDITOR = _load_prompt("security_auditor", _FALLBACK_SECURITY_AUDITOR)
        logger.info("System prompts reloaded from disk")

    @classmethod
    def custom(cls, prompt: str) -> str:
        """Get custom system prompt.

        Args:
            prompt: Custom prompt string

        Returns:
            The custom prompt string
        """
        return prompt

    @classmethod
    def from_file(cls, name: str) -> Optional[str]:
        """Load a prompt by name from the prompts directory.

        Args:
            name: Prompt file name (without .txt extension)

        Returns:
            Prompt text or None if file not found
        """
        path = _PROMPTS_DIR / f"{name}.txt"
        try:
            if path.exists():
                text = path.read_text(encoding="utf-8").strip()
                return text if text else None
        except Exception as e:
            logger.warning(f"Failed to load prompt {path}: {e}")
        return None

    @classmethod
    def for_role(cls, role: str) -> str:
        """Get system prompt based on user role.

        First tries to load from file prompts/{role}.txt,
        then falls back to predefined prompts.

        Args:
            role: User role (devops, developer, security, etc.)

        Returns:
            Appropriate system prompt for the role
        """
        # Try loading custom role prompt from file first
        custom = cls.from_file(role)
        if custom:
            return custom

        prompts = {
            "devops": cls.DEVOPS,
            "developer": cls.CODE_ASSISTANT,
            "security": cls.SECURITY_AUDITOR,
        }
        return prompts.get(role.lower(), cls.DEVOPS)
