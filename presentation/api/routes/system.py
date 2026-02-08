"""System information and metrics endpoints."""

import logging
import platform
import sys

from fastapi import APIRouter, Depends

from presentation.api.dependencies import get_container, get_system_monitor
from presentation.api.schemas.system import MetricsResponse, SystemInfoResponse
from presentation.api.security import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"], dependencies=[Depends(verify_api_key)])


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    summary="System information",
    description="Returns bot and system information.",
)
async def system_info() -> SystemInfoResponse:
    """Get system information."""
    container = get_container()

    # Check backends
    sdk_available = False
    sdk = container.claude_sdk()
    if sdk:
        try:
            sdk_available, _ = await sdk.check_sdk_available()
        except Exception:
            pass

    cli_available = False
    proxy = container.claude_proxy()
    try:
        cli_available, _ = await proxy.check_claude_installed()
    except Exception:
        pass

    return SystemInfoResponse(
        bot_username=getattr(container, "_bot_username", None),
        bot_id=getattr(container, "_bot_id", None),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        working_dir=container.config.claude_working_dir,
        sdk_available=sdk_available,
        cli_available=cli_available,
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="System metrics (JSON)",
    description="Returns system metrics in JSON format. "
    "For Prometheus format, use the /metrics endpoint on port 9090.",
)
async def system_metrics() -> MetricsResponse:
    """Get system metrics in JSON format."""
    try:
        monitor = get_system_monitor()
        metrics = await monitor.get_metrics()

        return MetricsResponse(
            cpu_percent=metrics.cpu_percent,
            memory_percent=metrics.memory_percent,
            memory_used_gb=metrics.memory_used_gb,
            disk_percent=metrics.disk_percent,
            load_avg_1m=metrics.load_avg_1,
        )
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return MetricsResponse()
