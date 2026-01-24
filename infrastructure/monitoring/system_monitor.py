import asyncio
import logging
import time
import psutil
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System resource metrics"""

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


class SystemMonitor:
    """System resource monitoring service"""

    def __init__(self, alert_thresholds: dict = None):
        self.thresholds = alert_thresholds or {
            "cpu": 80.0,
            "memory": 85.0,
            "disk": 90.0,
        }
        self._alerts = []

    async def get_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)

        # Disk
        disk = psutil.disk_usage("/")
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)

        # Load average (Unix-like systems)
        try:
            load1, load5, load15 = psutil.getloadavg()
            load_average = [load1, load5, load15]
        except (AttributeError, OSError):
            load_average = [0.0, 0.0, 0.0]

        # Uptime
        uptime_seconds = time.time() - psutil.boot_time()

        return SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_gb=round(memory_used_gb, 2),
            memory_total_gb=round(memory_total_gb, 2),
            disk_percent=disk.percent,
            disk_used_gb=round(disk_used_gb, 2),
            disk_total_gb=round(disk_total_gb, 2),
            load_average=load_average,
            uptime_seconds=round(uptime_seconds, 2),
        )

    async def get_top_processes(self, limit: int = 10) -> List[ProcessInfo]:
        """Get top processes by CPU and memory usage"""
        processes = []

        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent", "status", "cmdline"]
        ):
            try:
                proc_info = proc.info
                processes.append(
                    ProcessInfo(
                        pid=proc_info["pid"],
                        name=proc_info["name"] or "unknown",
                        cpu_percent=proc_info["cpu_percent"] or 0.0,
                        memory_percent=proc_info["memory_percent"] or 0.0,
                        status=proc_info["status"] or "unknown",
                        command=(
                            " ".join(proc_info["cmdline"])
                            if proc_info["cmdline"]
                            else ""
                        ),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU + memory usage
        processes.sort(key=lambda p: p.cpu_percent + p.memory_percent, reverse=True)
        return processes[:limit]

    async def check_alerts(self, metrics: SystemMetrics) -> List[str]:
        """Check if metrics exceed alert thresholds"""
        alerts = []

        if metrics.cpu_percent > self.thresholds["cpu"]:
            alerts.append(f"⚠️ High CPU usage: {metrics.cpu_percent:.1f}%")

        if metrics.memory_percent > self.thresholds["memory"]:
            alerts.append(f"⚠️ High memory usage: {metrics.memory_percent:.1f}%")

        if metrics.disk_percent > self.thresholds["disk"]:
            alerts.append(f"⚠️ High disk usage: {metrics.disk_percent:.1f}%")

        # Check load average
        if len(metrics.load_average) >= 3:
            cpu_count = psutil.cpu_count()
            if cpu_count and metrics.load_average[0] > cpu_count:
                alerts.append(
                    f"⚠️ High load average: {metrics.load_average[0]:.2f} (CPU cores: {cpu_count})"
                )

        return alerts

    async def get_docker_containers(self) -> List[dict]:
        """Get list of Docker containers with status"""
        try:
            import docker

            client = docker.from_env()
            containers = []

            for container in client.containers.list(all=True):
                containers.append(
                    {
                        "id": container.short_id,
                        "name": container.name,
                        "status": container.status,
                        "image": (
                            container.image.tags[0]
                            if container.image.tags
                            else str(container.image.id)
                        ),
                        "ports": (
                            [
                                f"{p['HostPort']}->{p['PrivatePort']}"
                                for p in container.ports.values()
                            ]
                            if container.ports
                            else []
                        ),
                    }
                )

            return containers
        except ImportError:
            logger.warning("docker module not installed")
            return []
        except Exception as e:
            logger.error(f"Error getting Docker containers: {e}")
            return []

    async def get_service_status(self, service_name: str) -> Optional[bool]:
        """Check if a systemd service is running"""
        try:
            from infrastructure.ssh.ssh_executor import SSHCommandExecutor

            executor = SSHCommandExecutor()
            result = await executor.execute(f"systemctl is-active {service_name}")
            return result.stdout.strip() == "active"
        except Exception as e:
            logger.error(f"Error checking service status: {e}")
            return None

    def format_metrics(self, metrics: SystemMetrics) -> str:
        """Format metrics for display"""
        uptime_hours = metrics.uptime_seconds / 3600

        lines = [
            "📊 **System Metrics**",
            "",
            f"💻 **CPU:** {metrics.cpu_percent:.1f}%",
            f"🧠 **Memory:** {metrics.memory_percent:.1f}% ({metrics.memory_used_gb}GB / {metrics.memory_total_gb}GB)",
            f"💾 **Disk:** {metrics.disk_percent:.1f}% ({metrics.disk_used_gb}GB / {metrics.disk_total_gb}GB)",
            f"⏱️ **Uptime:** {uptime_hours:.1f} hours",
        ]

        if metrics.load_average[0] > 0:
            lines.append(
                f"📈 **Load:** {metrics.load_average[0]:.2f} / {metrics.load_average[1]:.2f} / {metrics.load_average[2]:.2f}"
            )

        return "\n".join(lines)

    # ============== Docker Operations ==============

    async def docker_stop(self, container_id: str) -> tuple[bool, str]:
        """Stop a Docker container"""
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            container.stop()
            return True, f"Container {container.name} stopped"
        except ImportError:
            return False, "Docker module not installed"
        except Exception as e:
            return False, str(e)

    async def docker_start(self, container_id: str) -> tuple[bool, str]:
        """Start a Docker container"""
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            container.start()
            return True, f"Container {container.name} started"
        except ImportError:
            return False, "Docker module not installed"
        except Exception as e:
            return False, str(e)

    async def docker_restart(self, container_id: str) -> tuple[bool, str]:
        """Restart a Docker container"""
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            container.restart()
            return True, f"Container {container.name} restarted"
        except ImportError:
            return False, "Docker module not installed"
        except Exception as e:
            return False, str(e)

    async def docker_logs(self, container_id: str, lines: int = 50) -> tuple[bool, str]:
        """Get Docker container logs"""
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            logs = container.logs(tail=lines).decode('utf-8', errors='replace')
            return True, logs
        except ImportError:
            return False, "Docker module not installed"
        except Exception as e:
            return False, str(e)

    async def docker_remove(self, container_id: str, force: bool = False) -> tuple[bool, str]:
        """Remove a Docker container"""
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            name = container.name
            container.remove(force=force)
            return True, f"Container {name} removed"
        except ImportError:
            return False, "Docker module not installed"
        except Exception as e:
            return False, str(e)
