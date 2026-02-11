"""
FastAPI application factory.

Creates and configures the FastAPI app with all routes,
middleware, and dependency injection from the shared Container.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse

from shared.container import Container
from shared.logging.correlation import set_correlation_id, generate_correlation_id
from presentation.api.dependencies import set_container
from presentation.api.routes import health, projects, sessions, claude, system, config, auth, chat, upload
from presentation.api.routes import contexts, variables
from presentation.api.routes import websocket_route, docker_route
from presentation.api.routes import files, settings
from presentation.api.routes import gitlab
from presentation.api.routes import plugins, ssh

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

    # Correlation ID middleware for request tracing
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        # Accept correlation_id from header or generate new one
        cid = request.headers.get("X-Correlation-ID") or generate_correlation_id("api-")
        set_correlation_id(cid)
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response

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
    app.include_router(config.router, prefix=api_prefix)
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(upload.router, prefix=api_prefix)
    app.include_router(contexts.router, prefix=api_prefix)
    app.include_router(variables.router, prefix=api_prefix)
    app.include_router(websocket_route.router, prefix=api_prefix)
    app.include_router(files.router, prefix=api_prefix)
    app.include_router(settings.router, prefix=api_prefix)
    app.include_router(gitlab.router, prefix=api_prefix)
    app.include_router(docker_route.router, prefix=api_prefix)
    app.include_router(plugins.router, prefix=api_prefix)
    app.include_router(ssh.router, prefix=api_prefix)

    # Mount React SPA for admin panel
    # The SPA is built to static/admin/ by the Dockerfile frontend-build stage
    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static", "admin")
    static_dir = os.path.normpath(static_dir)

    if os.path.isdir(static_dir):
        # SPA catch-all: serve index.html for any /admin/* route not matched by static files.
        # This MUST be registered BEFORE the StaticFiles mount so that FastAPI
        # tries the explicit route first for paths that don't match a static file.
        @app.get("/admin/{full_path:path}")
        async def admin_spa_fallback(full_path: str):
            """Serve index.html for client-side routing in the React SPA."""
            index_path = os.path.join(static_dir, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
            return Response(content="Admin panel not found", status_code=404)

        # Mount static files for the admin SPA (serves JS, CSS, images, etc.)
        # html=True means it will serve index.html for directory requests (e.g., /admin/)
        app.mount("/admin", StaticFiles(directory=static_dir, html=True), name="admin-spa")
        logger.info(f"Admin SPA mounted at /admin from {static_dir}")
    else:
        logger.info(f"Admin SPA directory not found at {static_dir} — skipping mount")

    logger.info(
        f"REST API configured: {len(app.routes)} routes, "
        f"docs at /docs, API at {api_prefix}"
    )

    return app
