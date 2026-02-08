# Spec-Kit: Initialize Project

Initialize a new Spec-Driven Development (SDD) project using GitHub Spec Kit.

## Arguments
- `$ARGUMENTS` - Project name and options (e.g., "my-project --ai claude")

## Instructions

Run the specify init command with the provided arguments:

```bash
specify init $ARGUMENTS
```

If no arguments provided, show available options and ask user what they want.

### Available AI options:
- `claude` - Claude Code (recommended)
- `copilot` - GitHub Copilot
- `gemini` - Google Gemini
- `cursor-agent` - Cursor
- `codex` - OpenAI Codex
- `windsurf` - Windsurf

### Examples:
- `/spec-init my-project --ai claude`
- `/spec-init --here --ai claude`
- `/spec-init . --ai copilot`
