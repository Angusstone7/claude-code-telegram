"""
File Browser Service

Application service for navigating the file system with a visual tree view.
Used by the /cd command for interactive folder navigation.
"""

import html
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DirectoryEntry:
    """Represents a file or folder in a directory"""
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None


@dataclass
class DirectoryContent:
    """Contents of a directory for navigation"""
    path: str
    parent_path: Optional[str]
    entries: List[DirectoryEntry]
    is_root: bool


class FileBrowserService:
    """
    Service for navigating the file system.

    Features:
    - List directory contents
    - Generate HTML tree view with emojis
    - Path validation (security)
    - File type detection for emojis
    """

    ROOT_PATH = "/root/projects"
    MAX_ENTRIES = 50  # Limit displayed entries
    MAX_DEPTH = 3     # Max tree depth for display

    def __init__(self, root_path: str = None):
        if root_path:
            self.ROOT_PATH = root_path

    async def list_directory(self, path: str) -> DirectoryContent:
        """
        Get contents of a directory.

        Args:
            path: Directory path to list

        Returns:
            DirectoryContent with entries and metadata
        """
        # Normalize and validate path
        path = self._normalize_path(path)

        if not self.is_within_root(path):
            logger.warning(f"Access denied: {path} is outside root")
            path = self.ROOT_PATH

        # Ensure directory exists
        if not os.path.isdir(path):
            logger.warning(f"Directory not found: {path}")
            path = self.ROOT_PATH

        # Create root if it doesn't exist
        os.makedirs(self.ROOT_PATH, exist_ok=True)

        # Get entries
        entries = []
        try:
            for entry in os.scandir(path):
                # Skip hidden files
                if entry.name.startswith('.'):
                    continue

                try:
                    size = entry.stat().st_size if entry.is_file() else None
                    entries.append(DirectoryEntry(
                        name=entry.name,
                        path=entry.path,
                        is_dir=entry.is_dir(),
                        size=size
                    ))
                except OSError:
                    continue

                # Limit entries
                if len(entries) >= self.MAX_ENTRIES:
                    break

        except PermissionError:
            logger.error(f"Permission denied: {path}")
        except OSError as e:
            logger.error(f"Error reading directory {path}: {e}")

        # Sort: folders first, then files, alphabetically
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))

        # Determine parent path
        parent_path = self.get_parent_path(path)

        return DirectoryContent(
            path=path,
            parent_path=parent_path,
            entries=entries,
            is_root=(path == self.ROOT_PATH)
        )

    async def get_tree_view(self, path: str, max_depth: int = 1) -> str:
        """
        Generate HTML tree view of directory.

        Args:
            path: Directory path
            max_depth: How deep to show nested structure

        Returns:
            HTML-formatted tree string
        """
        content = await self.list_directory(path)
        return self._build_tree_html(content, max_depth)

    def is_within_root(self, path: str) -> bool:
        """
        Check if path is within allowed root directory.

        Args:
            path: Path to check

        Returns:
            True if path is safe
        """
        try:
            # Normalize both paths
            normalized = os.path.normpath(os.path.abspath(path))
            root_normalized = os.path.normpath(os.path.abspath(self.ROOT_PATH))

            # Check if path starts with root
            return normalized.startswith(root_normalized) or normalized == root_normalized
        except Exception:
            return False

    def get_parent_path(self, path: str) -> Optional[str]:
        """
        Get parent directory path.

        Args:
            path: Current path

        Returns:
            Parent path or None if at root
        """
        path = self._normalize_path(path)

        if path == self.ROOT_PATH:
            return None

        parent = os.path.dirname(path)

        # Don't go above root
        if not self.is_within_root(parent):
            return None

        return parent

    def resolve_path(self, current_dir: str, target: str) -> str:
        """
        Resolve a relative or absolute path.

        Args:
            current_dir: Current working directory
            target: Target path (can be relative)

        Returns:
            Resolved absolute path
        """
        if target == "..":
            parent = self.get_parent_path(current_dir)
            return parent if parent else self.ROOT_PATH

        if target == "~" or target == "/":
            return self.ROOT_PATH

        if target.startswith("/"):
            # Absolute path
            resolved = target
        else:
            # Relative path
            resolved = os.path.join(current_dir, target)

        resolved = self._normalize_path(resolved)

        if not self.is_within_root(resolved):
            return self.ROOT_PATH

        return resolved

    def _normalize_path(self, path: str) -> str:
        """Normalize a path"""
        return os.path.normpath(os.path.abspath(path))

    def _build_tree_html(
        self,
        content: DirectoryContent,
        max_depth: int = 1,
        current_depth: int = 0
    ) -> str:
        """
        Build HTML tree representation.

        Args:
            content: Directory content
            max_depth: Maximum depth to show
            current_depth: Current recursion depth

        Returns:
            HTML string
        """
        lines = []

        # Header with path
        lines.append(f"📂 <b>{html.escape(content.path)}</b>\n")

        if not content.entries:
            lines.append("   <i>(пусто)</i>")
        else:
            # Build tree
            for i, entry in enumerate(content.entries):
                is_last = (i == len(content.entries) - 1)
                branch = "└── " if is_last else "├── "

                emoji = self._get_emoji(entry)

                if entry.is_dir:
                    name = f"<b>{html.escape(entry.name)}</b>"
                else:
                    name = html.escape(entry.name)
                    # Add size for files
                    if entry.size is not None:
                        size_str = self._format_size(entry.size)
                        name += f" <i>({size_str})</i>"

                lines.append(f"{branch}{emoji} {name}")

        # Footer with current path
        lines.append(f"\n📍 <b>Путь:</b> <code>{html.escape(content.path)}</code>")

        # Show if truncated
        if len(content.entries) >= self.MAX_ENTRIES:
            lines.append(f"<i>... и ещё файлы (показано {self.MAX_ENTRIES})</i>")

        return "\n".join(lines)

    def _get_emoji(self, entry: DirectoryEntry) -> str:
        """
        Get emoji for file/folder.

        Args:
            entry: Directory entry

        Returns:
            Emoji string
        """
        if entry.is_dir:
            return "📁"

        filename = entry.name.lower()

        # Special files
        special_files = {
            'dockerfile': '🐳',
            'docker-compose.yml': '🐳',
            'docker-compose.yaml': '🐳',
            'requirements.txt': '📦',
            'package.json': '📦',
            'package-lock.json': '🔒',
            'yarn.lock': '🔒',
            'readme.md': '📖',
            'readme': '📖',
            'license': '📜',
            'license.md': '📜',
            'makefile': '⚙️',
            '.env': '🔐',
            '.env.example': '🔐',
            '.gitignore': '📦',
            '.dockerignore': '🐳',
        }

        if filename in special_files:
            return special_files[filename]

        # By extension
        ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''

        emoji_map = {
            # Programming
            'py': '🐍',
            'js': '📜',
            'ts': '📘',
            'jsx': '⚛️',
            'tsx': '⚛️',
            'go': '🔵',
            'rs': '🦀',
            'java': '☕',
            'kt': '🟣',
            'swift': '🍎',
            'c': '🔧',
            'cpp': '🔧',
            'h': '🔧',
            'cs': '💜',
            'rb': '💎',
            'php': '🐘',

            # Web
            'html': '🌐',
            'css': '🎨',
            'scss': '🎨',
            'sass': '🎨',
            'less': '🎨',
            'vue': '💚',
            'svelte': '🧡',

            # Data
            'json': '📋',
            'yaml': '📋',
            'yml': '📋',
            'xml': '📋',
            'csv': '📊',
            'sql': '🗃️',
            'db': '🗃️',
            'sqlite': '🗃️',

            # Config
            'toml': '⚙️',
            'ini': '⚙️',
            'cfg': '⚙️',
            'conf': '⚙️',

            # Docs
            'md': '📝',
            'txt': '📄',
            'rst': '📝',
            'pdf': '📕',
            'doc': '📘',
            'docx': '📘',

            # Shell
            'sh': '⚙️',
            'bash': '⚙️',
            'zsh': '⚙️',
            'fish': '⚙️',
            'bat': '⚙️',
            'cmd': '⚙️',
            'ps1': '⚙️',

            # Images
            'png': '🖼️',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'gif': '🖼️',
            'svg': '🖼️',
            'ico': '🖼️',
            'webp': '🖼️',

            # Archives
            'zip': '📦',
            'tar': '📦',
            'gz': '📦',
            'rar': '📦',
            '7z': '📦',

            # Other
            'log': '📋',
            'lock': '🔒',
            'env': '🔐',
            'key': '🔑',
            'pem': '🔑',
            'crt': '🔑',
        }

        return emoji_map.get(ext, '📄')

    def _format_size(self, size: int) -> str:
        """Format file size for display"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
