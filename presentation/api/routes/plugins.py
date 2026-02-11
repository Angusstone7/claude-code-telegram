"""Plugin management endpoints."""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends

from presentation.api.dependencies import get_container
from presentation.api.schemas.plugins import (
    PluginCommand,
    PluginListResponse,
    PluginResponse,
)
from presentation.api.security import hybrid_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plugins", tags=["Plugins"])


def _scan_plugin_dir(plugin_path: str) -> list[PluginCommand]:
    """Scan a local plugin directory for commands.

    Looks for COMMANDS.md or package.json to extract available slash commands.
    Falls back to listing .md files in the directory that look like command docs.
    """
    commands: list[PluginCommand] = []

    # Try COMMANDS.md (common in anthropic/claude-plugins-official)
    commands_md = os.path.join(plugin_path, "COMMANDS.md")
    if os.path.isfile(commands_md):
        try:
            with open(commands_md, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Parse lines like "- `/command` — description"
                    if line.startswith("- `/") or line.startswith("* `/"):
                        # Extract command name between backticks
                        parts = line.split("`")
                        if len(parts) >= 2:
                            cmd_name = parts[1].strip("/").strip()
                            # Description after the backtick section
                            desc_parts = line.split("—")
                            if len(desc_parts) < 2:
                                desc_parts = line.split("-", 2)
                            desc = desc_parts[-1].strip() if len(desc_parts) > 1 else None
                            commands.append(PluginCommand(name=cmd_name, description=desc))
        except Exception as e:
            logger.debug(f"Error reading COMMANDS.md at {commands_md}: {e}")

    # Try package.json for metadata
    package_json = os.path.join(plugin_path, "package.json")
    if os.path.isfile(package_json) and not commands:
        try:
            with open(package_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
                # Some plugins define commands in package.json
                if "commands" in pkg:
                    for cmd in pkg["commands"]:
                        if isinstance(cmd, dict):
                            commands.append(PluginCommand(
                                name=cmd.get("name", ""),
                                description=cmd.get("description"),
                            ))
                        elif isinstance(cmd, str):
                            commands.append(PluginCommand(name=cmd))
        except Exception as e:
            logger.debug(f"Error reading package.json at {package_json}: {e}")

    # Fallback: scan for .md files that look like command documentation
    if not commands:
        try:
            for entry in os.listdir(plugin_path):
                if entry.endswith(".md") and entry not in ("README.md", "COMMANDS.md"):
                    cmd_name = entry.replace(".md", "")
                    commands.append(PluginCommand(name=cmd_name))
        except Exception:
            pass

    return commands


def _get_plugin_description(plugin_path: str, plugin_name: str) -> Optional[str]:
    """Try to extract description from plugin metadata."""
    # Known descriptions
    known_descriptions = {
        "commit-commands": "Git workflow: commit, push, PR",
        "code-review": "Code review and PR analysis",
        "feature-dev": "Feature development with architecture",
        "frontend-design": "UI interface creation",
        "claude-code-setup": "Claude Code setup and configuration",
        "security-guidance": "Security code review",
        "pr-review-toolkit": "PR review toolkit",
        "ralph-loop": "RAFL: iterative problem solving",
    }

    if plugin_name in known_descriptions:
        return known_descriptions[plugin_name]

    # Try package.json
    package_json = os.path.join(plugin_path, "package.json")
    if os.path.isfile(package_json):
        try:
            with open(package_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
                return pkg.get("description")
        except Exception:
            pass

    # Try README.md first line
    readme = os.path.join(plugin_path, "README.md")
    if os.path.isfile(readme):
        try:
            with open(readme, "r", encoding="utf-8") as f:
                first_line = f.readline().strip().lstrip("# ")
                if first_line:
                    return first_line[:200]
        except Exception:
            pass

    return None


@router.get(
    "",
    response_model=PluginListResponse,
    summary="List Claude Code plugins",
    description="Returns all available Claude Code plugins with enabled/disabled status and commands.",
)
async def list_plugins(
    _user: dict = Depends(hybrid_auth),
) -> PluginListResponse:
    """List all available plugins."""
    container = get_container()
    sdk = container.claude_sdk()

    plugins_dir = container.config.claude_plugins_dir
    enabled_raw = [
        p.strip()
        for p in container.config.claude_plugins.split(",")
        if p.strip()
    ]

    # Normalize enabled plugin names (strip prefixes)
    enabled_names: set[str] = set()
    for name in enabled_raw:
        if name.startswith("official:") or name.startswith("local:"):
            enabled_names.add(name.split(":", 1)[1])
        else:
            enabled_names.add(name)

    plugins: list[PluginResponse] = []
    seen_names: set[str] = set()

    # 1. Use SDK service info if available (it has richer metadata)
    if sdk:
        try:
            for info in sdk.get_enabled_plugins_info():
                name = info["name"]
                seen_names.add(name)
                plugin_path = info.get("path") or os.path.join(plugins_dir, name)
                commands = _scan_plugin_dir(plugin_path) if os.path.isdir(plugin_path) else []

                plugins.append(PluginResponse(
                    name=name,
                    enabled=True,
                    description=info.get("description"),
                    source=info.get("source", "local"),
                    commands=commands,
                ))
        except Exception as e:
            logger.warning(f"Error getting SDK plugin info: {e}")

    # 2. Scan plugins directory for all available plugins (including disabled ones)
    if os.path.isdir(plugins_dir):
        try:
            for entry in sorted(os.listdir(plugins_dir)):
                entry_path = os.path.join(plugins_dir, entry)
                if os.path.isdir(entry_path) and not entry.startswith(".") and entry not in seen_names:
                    seen_names.add(entry)
                    commands = _scan_plugin_dir(entry_path)
                    description = _get_plugin_description(entry_path, entry)

                    plugins.append(PluginResponse(
                        name=entry,
                        enabled=entry in enabled_names,
                        description=description,
                        source="local",
                        commands=commands,
                    ))
        except Exception as e:
            logger.warning(f"Error scanning plugins directory {plugins_dir}: {e}")

    # 3. Add enabled plugins that are official (not found locally)
    for name in enabled_names:
        if name not in seen_names:
            seen_names.add(name)
            plugins.append(PluginResponse(
                name=name,
                enabled=True,
                description=None,
                source="official",
                commands=[],
            ))

    return PluginListResponse(plugins=plugins, total=len(plugins))
