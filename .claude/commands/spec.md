# Spec-Kit: Main Command

GitHub Spec Kit - Spec-Driven Development Toolkit.

## Arguments
- `$ARGUMENTS` - Subcommand and options

## Instructions

If arguments provided, run:
```bash
specify $ARGUMENTS
```

If no arguments, show help:
```bash
specify --help
```

### Available subcommands:
- `init [name]` - Initialize new SDD project
- `check` - Check environment tools
- `version` - Show version info

### Quick examples:
- `/spec init my-app --ai claude` - Create new project
- `/spec check` - Verify environment
- `/spec version` - Show version
