"""FastAPI application factory for agent-inference-stack.

This module creates and configures the FastAPI application with all
middleware, routes, exception handlers, and lifespan management.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import __version__
from src.api.middleware import RequestIDMiddleware, RequestLoggingMiddleware
from src.api.routes import router
from src.api.schemas import ErrorResponse
from src.config import get_settings
from src.logging_config import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown of all application components:
    - Configures logging
    - Initializes Redis connection
    - Initializes PostgreSQL connection pool
    - Initializes the Orchestrator
    - Registers all agents
    """
    settings = get_settings()
    configure_logging(level=settings.log_level, environment=settings.app_env)
    log = structlog.get_logger(__name__)

    log.info("starting_up", version=__version__, environment=settings.app_env)

    # Initialize orchestrator (lazy import to avoid circular deps)
    try:
        from src.orchestration.orchestrator import Orchestrator

        orchestrator = Orchestrator(settings=settings)
        await orchestrator.initialize()
        app.state.orchestrator = orchestrator
        app.state.environment = settings.app_env
        log.info("orchestrator_initialized")
    except Exception as e:
        log.error("orchestrator_init_failed", error=str(e))
        app.state.orchestrator = None

    # Initialize Redis if configured
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_db,
            decode_responses=True,
        )
        await redis_client.ping()
        app.state.redis = redis_client
        log.info("redis_connected", host=settings.redis_host, port=settings.redis_port)
    except Exception as e:
        log.warning("redis_connection_failed", error=str(e))
        app.state.redis = None

    log.info("startup_complete", version=__version__)
    yield

    # Shutdown
    log.info("shutting_down")
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.aclose()
        log.info("redis_disconnected")
    if hasattr(app.state, "orchestrator") and app.state.orchestrator:
        await app.state.orchestrator.shutdown()
        log.info("orchestrator_shutdown")
    log.info("shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="agent-inference-stack",
        description=(
            "Multi-agent AI system with Dynamo token batching, "
            "vLLM inference, and Kubernetes orchestration"
        ),
        version=__version__,
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (order matters — added last, executes first)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="Internal server error",
                detail=str(exc) if settings.app_debug else None,
                request_id=request_id,
            ).model_dump(mode="json"),
        )

    # Root health check
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {"service": "agent-inference-stack", "version": __version__, "status": "running"}

    # Include API routes
    app.include_router(router, prefix="/api/v1", tags=["Agent Inference Stack"])

    return app


app = create_app()


def main() -> None:
    """Entry point for running the server."""
    settings = get_settings()
    uvicorn.run(
        "src.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
        workers=1 if settings.app_debug else 4,
    )


if __name__ == "__main__":
    main()
