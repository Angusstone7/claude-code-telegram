"""System prompts for AI service

Domain-level prompts define the behavior and personality of the AI assistant.
These are pure domain objects, independent of any infrastructure implementation.
"""


class SystemPrompts:
    """Predefined system prompts for different use cases

    This class provides factory methods for getting system prompts
    based on the use case. It follows the Open/Closed Principle -
    open for extension (add new prompt types), closed for modification.
    """

    DEVOPS = """You are an intelligent DevOps assistant with access to a Linux server via SSH.
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

You have access to bash command execution tool. Use it to help the user.
"""

    CODE_ASSISTANT = """You are an expert programmer and code assistant.
You can help with:
- Writing and reviewing code
- Debugging and troubleshooting
- Code optimization and refactoring
- Explaining code and concepts

Provide clear, concise explanations and well-structured code examples."""

    SECURITY_AUDITOR = """You are a security specialist focused on identifying and explaining security issues.
When analyzing systems or code:
1. Identify potential vulnerabilities
2. Explain the risks clearly
3. Suggest remediation steps
4. Prioritize issues by severity"""

    @classmethod
    def custom(cls, prompt: str) -> str:
        """Get custom system prompt

        Args:
            prompt: Custom prompt string

        Returns:
            The custom prompt string
        """
        return prompt

    @classmethod
    def for_role(cls, role: str) -> str:
        """Get system prompt based on user role

        Args:
            role: User role (devops, developer, security, etc.)

        Returns:
            Appropriate system prompt for the role
        """
        prompts = {
            "devops": cls.DEVOPS,
            "developer": cls.CODE_ASSISTANT,
            "security": cls.SECURITY_AUDITOR,
        }
        return prompts.get(role.lower(), cls.DEVOPS)
