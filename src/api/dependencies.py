"""FastAPI dependency injection providers."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status

logger = structlog.get_logger(__name__)

# Lazy imports to avoid circular dependencies at startup
_orchestrator_instance = None


async def get_orchestrator():
    """Dependency that provides the global orchestrator instance.

    The orchestrator is initialized at application startup and
    reused across all requests.

    Raises:
        HTTPException: 503 if orchestrator is not yet initialized.
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized. Service is starting up.",
        )
    return _orchestrator_instance


def set_orchestrator(orchestrator) -> None:
    """Set the global orchestrator instance (called at startup)."""
    global _orchestrator_instance
    _orchestrator_instance = orchestrator


OrchestratorDep = Annotated[object, Depends(get_orchestrator)]
