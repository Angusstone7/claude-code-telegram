"""Docker container management endpoints."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from presentation.api.schemas.docker_schemas import (
    ContainerActionResponse,
    ContainerListResponse,
    ContainerLogsResponse,
    ContainerResponse,
)
from presentation.api.security import hybrid_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/docker", tags=["Docker"])


# ── Helpers ───────────────────────────────────────────────────────────────


class ContainerAction(str, Enum):
    """Allowed container actions."""

    start = "start"
    stop = "stop"
    restart = "restart"


def _get_docker_client():
    """Lazily import and return the Docker client (from-env)."""
    try:
        import docker  # type: ignore

        return docker.from_env()
    except Exception as exc:
        logger.error("Failed to connect to Docker daemon: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Docker daemon unavailable: {exc}",
        )


def _format_ports(container) -> list[str]:
    """Convert Docker port dict to human-readable list."""
    ports_info: list[str] = []
    try:
        ports = container.attrs.get("NetworkSettings", {}).get("Ports") or {}
        for container_port, bindings in ports.items():
            if bindings:
                for b in bindings:
                    host = b.get("HostIp", "0.0.0.0")
                    host_port = b.get("HostPort", "")
                    ports_info.append(f"{host}:{host_port}->{container_port}")
            else:
                ports_info.append(container_port)
    except Exception:
        pass
    return ports_info


def _format_uptime(container) -> Optional[str]:
    """Extract human-readable uptime from container status."""
    try:
        state = container.attrs.get("State", {})
        status_str = state.get("Status", "")
        if status_str == "running":
            started = state.get("StartedAt", "")
            if started:
                from datetime import datetime, timezone

                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - started_dt
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                parts = []
                if days > 0:
                    parts.append(f"{days}d")
                if hours > 0:
                    parts.append(f"{hours}h")
                parts.append(f"{minutes}m")
                return " ".join(parts)
    except Exception:
        pass
    return None


def _format_created_at(container):
    """Parse the Created timestamp."""
    try:
        created = container.attrs.get("Created", "")
        if created:
            from datetime import datetime

            return datetime.fromisoformat(created.replace("Z", "+00:00"))
    except Exception:
        pass
    return None


def _container_to_response(container) -> ContainerResponse:
    """Convert a Docker container object to a ContainerResponse."""
    return ContainerResponse(
        name=container.name or "",
        status=container.status or "unknown",
        image=",".join(container.image.tags) if container.image and container.image.tags else str(container.image),
        ports=_format_ports(container),
        uptime=_format_uptime(container),
        created_at=_format_created_at(container),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get(
    "/containers",
    response_model=ContainerListResponse,
    summary="List all Docker containers",
    description="Returns all containers (running + stopped).",
)
async def list_containers(
    user: dict = Depends(hybrid_auth),
) -> ContainerListResponse:
    """List all Docker containers."""
    client = _get_docker_client()
    try:
        containers = client.containers.list(all=True)
        items = [_container_to_response(c) for c in containers]
        return ContainerListResponse(containers=items, total=len(items))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list containers: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list containers: {exc}",
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


@router.post(
    "/containers/{name}/{action}",
    response_model=ContainerActionResponse,
    summary="Perform action on a container",
    description="Start, stop, or restart a Docker container by name.",
)
async def container_action(
    name: str,
    action: ContainerAction,
    user: dict = Depends(hybrid_auth),
) -> ContainerActionResponse:
    """Perform start / stop / restart on a container."""
    # Only admin can manage Docker containers
    if user.get("role") != "admin" and user.get("auth_method") not in ("api_key", "none"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to manage Docker containers.",
        )

    client = _get_docker_client()
    try:
        try:
            container = client.containers.get(name)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container '{name}' not found.",
            )

        if action == ContainerAction.start:
            container.start()
            message = f"Container '{name}' started."
        elif action == ContainerAction.stop:
            container.stop()
            message = f"Container '{name}' stopped."
        elif action == ContainerAction.restart:
            container.restart()
            message = f"Container '{name}' restarted."
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {action}",
            )

        logger.info("Docker action %s on container %s by user %s", action.value, name, user.get("username"))

        return ContainerActionResponse(
            name=name,
            action=action.value,
            success=True,
            message=message,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to %s container %s: %s", action.value, name, exc)
        return ContainerActionResponse(
            name=name,
            action=action.value,
            success=False,
            message=str(exc),
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


@router.get(
    "/containers/{name}/logs",
    response_model=ContainerLogsResponse,
    summary="Get container logs",
    description="Returns the tail of a container's log output.",
)
async def container_logs(
    name: str,
    tail: int = Query(100, ge=1, le=10000, description="Number of log lines to return"),
    user: dict = Depends(hybrid_auth),
) -> ContainerLogsResponse:
    """Get container logs."""
    client = _get_docker_client()
    try:
        try:
            container = client.containers.get(name)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container '{name}' not found.",
            )

        logs_bytes = container.logs(tail=tail, timestamps=False)
        if isinstance(logs_bytes, bytes):
            logs_text = logs_bytes.decode("utf-8", errors="replace")
        else:
            logs_text = str(logs_bytes)

        lines_count = logs_text.count("\n") + (1 if logs_text and not logs_text.endswith("\n") else 0)

        return ContainerLogsResponse(
            name=name,
            logs=logs_text,
            lines=lines_count,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get logs for container %s: %s", name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get logs: {exc}",
        )
    finally:
        try:
            client.close()
        except Exception:
            pass
