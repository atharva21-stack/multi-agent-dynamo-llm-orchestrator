"""Structured logging configuration for agent-inference-stack.

Sets up structlog with JSON output in production and pretty console
output in development.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(level: str = "INFO", environment: str = "development") -> None:
    """Configure structured logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        environment: Application environment for format selection.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "production":
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs use our format
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named structured logger.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured structlog bound logger.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("processing_request", request_id="abc123", agent="planning")
    """
    return structlog.get_logger(name)
