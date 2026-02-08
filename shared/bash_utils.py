"""
Bash command utilities.

Shared logic for detecting directory changes in bash commands.
Extracted from messages.py and ai_request_handler.py to eliminate duplication.
"""

import os
import re
from typing import Optional


def detect_cd_command(command: str, current_dir: str) -> Optional[str]:
    """
    Detect if a bash command changes directory and return the new absolute path.

    Handles patterns like:
    - cd /path/to/dir
    - cd subdir
    - mkdir -p dir && cd dir
    - cd ~
    - cd ..
    - cd -  (returns None — previous dir unknown)

    Args:
        command: The bash command string to analyze.
        current_dir: The current working directory.

    Returns:
        The new directory path if cd detected, None otherwise.
    """
    cd_patterns = [
        r'(?:^|&&|;)\s*cd\s+([^\s;&|]+)',
        r'(?:^|&&|;)\s*cd\s+"([^"]+)"',
        r"(?:^|&&|;)\s*cd\s+'([^']+)'",
    ]

    new_dir = None
    for pattern in cd_patterns:
        matches = re.findall(pattern, command)
        if matches:
            new_dir = matches[-1]
            break

    if not new_dir:
        return None

    if new_dir.startswith('/'):
        return new_dir
    elif new_dir == '~':
        return os.path.expanduser('~')
    elif new_dir == '-':
        return None  # Previous directory is unknown
    elif new_dir == '..':
        return os.path.dirname(current_dir)
    else:
        return os.path.join(current_dir, new_dir)
