"""Reusable project logger."""

import logging
import sys
from pathlib import Path


_LOGGER_NAME = "whatsapp_router"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a project-scoped logger instance.

    Args:
        name: Optional suffix appended to the base logger name.

    Returns:
        Configured logger instance.
    """
    logger_name = _LOGGER_NAME if name is None else f"{_LOGGER_NAME}.{name}"
    return logging.getLogger(logger_name)


def setup_logger(
    level: str = "INFO",
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure and return the root project logger.

    Args:
        level: Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
        log_file: Optional file path for log output.

    Returns:
        Configured root project logger.
    """
    logger = get_logger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
