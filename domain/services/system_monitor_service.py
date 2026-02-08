"""
System Monitor Service Interface

Defines the contract for system monitoring, independent of implementation
(local psutil, SSH-based, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SystemMetrics:
    """System resource metrics (domain-level value object)"""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    load_average: List[float]
    uptime_seconds: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_gb": self.memory_used_gb,
            "memory_total_gb": self.memory_total_gb,
            "disk_percent": self.disk_percent,
            "disk_used_gb": self.disk_used_gb,
            "disk_total_gb": self.disk_total_gb,
            "load_average": self.load_average,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class ProcessInfo:
    """Information about a running process"""

    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    command: str


class ISystemMonitor(ABC):
    """Interface for system monitoring services"""

    @abstractmethod
    async def get_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        pass

    @abstractmethod
    async def get_top_processes(self, limit: int = 10) -> List[ProcessInfo]:
        """Get top processes by resource usage"""
        pass

    @abstractmethod
    async def check_alerts(self, metrics: SystemMetrics) -> List[Dict]:
        """Check metrics against thresholds and return alerts"""
        pass

    @abstractmethod
    async def get_docker_status(self) -> Optional[Dict]:
        """Get Docker container status (if available)"""
        pass
