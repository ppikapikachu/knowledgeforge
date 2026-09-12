"""Logging configuration."""

import logging
import sys
from typing import Optional

from app.core.config import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """Configure application logging."""
    level = log_level or ("DEBUG" if settings.DEBUG else "INFO")

    # Define log format
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "%(request_id)s | %(message)s"
    )

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress noisy loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestIdFilter(logging.Filter):
    """Logging filter that adds request_id to log records."""

    def __init__(self, request_id: str = "-"):
        super().__init__()
        self.request_id = request_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", "-")
        return True
