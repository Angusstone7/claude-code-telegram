"""
Diagnostics Service Interface

Defines the contract for running diagnostics on Claude Code CLI/SDK.
"""

from abc import ABC, abstractmethod
from typing import Dict


class IDiagnosticsService(ABC):
    """Interface for diagnostics services"""

    @abstractmethod
    async def run_diagnostics(self) -> Dict:
        """Run comprehensive diagnostics. Returns dict with test results."""
        pass

    @abstractmethod
    def format_for_telegram(self, results: Dict) -> str:
        """Format diagnostics results for Telegram display"""
        pass
