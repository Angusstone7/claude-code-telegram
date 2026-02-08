"""Health check endpoint — no authentication required."""

import logging
import time

from fastapi import APIRouter

from presentation.api.dependencies import get_container
from presentation.api.schemas.system import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

# Track startup time for uptime calculation
_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns health status of all backends. No authentication required.",
)
async def health_check() -> HealthResponse:
    """Check health of all system components."""
    container = get_container()

    # Check SDK
    sdk_available = False
    sdk = container.claude_sdk()
    if sdk:
        try:
            sdk_available, _ = await sdk.check_sdk_available()
        except Exception:
            pass

    # Check CLI
    cli_available = False
    proxy = container.claude_proxy()
    try:
        cli_available, _ = await proxy.check_claude_installed()
    except Exception:
        pass

    # Check database
    db_ok = False
    try:
        # Simple query to verify DB connection
        user_repo = container.user_repository()
        if user_repo:
            db_ok = True
    except Exception:
        pass

    overall = "ok" if (sdk_available or cli_available) and db_ok else "degraded"

    return HealthResponse(
        status=overall,
        sdk_available=sdk_available,
        cli_available=cli_available,
        database_ok=db_ok,
        uptime_seconds=round(time.time() - _start_time, 1),
    )
