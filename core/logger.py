"""
Structured logging for West Africa Financial Intelligence Agent.
"""

import logging
import sys
from typing import Any

from core.config import settings


def setup_logging(
    level: str | None = None,
    format_string: str | None = None,
) -> logging.Logger:
    """Configure application logging."""
    level = level or settings.LOG_LEVEL
    format_string = format_string or (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    )

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Reduce noise from third-party libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    return logging.getLogger(settings.PROJECT_NAME)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(f"{settings.PROJECT_NAME}.{name}")


def log_error(logger: logging.Logger, msg: str, exc: BaseException | None = None, **kwargs: Any) -> None:
    """Log error with optional exception."""
    if exc:
        logger.exception(msg, exc_info=exc, extra=kwargs)
    else:
        logger.error(msg, extra=kwargs)
