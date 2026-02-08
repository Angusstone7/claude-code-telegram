"""
FastAPI application factory.

Creates and configures the FastAPI app with all routes,
middleware, and dependency injection from the shared Container.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.container import Container
from presentation.api.dependencies import set_container
from presentation.api.routes import health, projects, sessions, claude, system

logger = logging.getLogger(__name__)


def create_app(container: Container) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        container: DI container with all services initialized.

    Returns:
        Configured FastAPI application.
    """
    # Wire container into FastAPI dependency system
    set_container(container)

    app = FastAPI(
        title="Ubuntu Claude Bot API",
        description=(
            "REST API for the Ubuntu Claude Bot. Provides programmatic access to "
            "projects, sessions, Claude task execution, and system monitoring.\n\n"
            "**Authentication:** Pass `X-API-Key` header. If `API_KEY` env var is not set, "
            "authentication is disabled (development mode)."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware for browser access to Swagger UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules under /api/v1 prefix
    api_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(projects.router, prefix=api_prefix)
    app.include_router(sessions.router, prefix=api_prefix)
    app.include_router(claude.router, prefix=api_prefix)
    app.include_router(system.router, prefix=api_prefix)

    logger.info(
        f"REST API configured: {len(app.routes)} routes, "
        f"docs at /docs, API at {api_prefix}"
    )

    return app
