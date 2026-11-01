"""
Structured JSON logging configuration.

Outputs structured JSON to stdout so cloud log collectors (CloudWatch,
Stackdriver, Datadog, etc.) can parse logs without custom parsers.
Includes request IDs for tracing requests across services.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
try:
    from pythonjsonlogger import json as jsonlogger
except ImportError:
    from pythonjsonlogger import jsonlogger

# Context variable to store the current request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Injects the current request_id into every log record."""

    def filter(self, record):
        record.request_id = request_id_ctx.get("-")
        return True


def generate_request_id() -> str:
    """Generate a short unique request ID."""
    return uuid.uuid4().hex[:12]


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure the root logger with structured JSON output.

    Call this once at application startup (in main.py).
    """
    # Create a JSON formatter
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers (avoid duplicates on reload)
    root_logger.handlers.clear()

    # Add a stdout handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    root_logger.addHandler(handler)

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
