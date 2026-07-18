"""Application logging configuration for CompanyLocationEnricher."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import Config


APPLICATION_LOGGER_NAME = "company_location_enricher"
LOG_FILE_NAME = "company_location_enricher.log"
MAX_LOG_FILE_BYTES = 5 * 1024 * 1024
BACKUP_LOG_FILE_COUNT = 5
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(module)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_HANDLER_MARKER = "_company_location_enricher_handler"


def configure_logging(config: Config) -> logging.Logger:
    """Configure and return the application logger.

    The returned logger writes all standard Python logging levels to a rotating
    UTF-8 log file and to the console's error stream. Repeated calls replace
    only handlers created by this module, preventing duplicate log lines while
    preserving logging configured by other libraries.

    Args:
        config: Validated application configuration containing ``log_directory``.

    Returns:
        A fully configured application :class:`logging.Logger`.

    Raises:
        OSError: If the log directory or log file cannot be created.
    """

    log_directory = Path(config.log_directory)
    log_directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(APPLICATION_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    _remove_configured_handlers(logger)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_directory / LOG_FILE_NAME,
        maxBytes=MAX_LOG_FILE_BYTES,
        backupCount=BACKUP_LOG_FILE_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    _mark_handler(console_handler)
    _mark_handler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def _remove_configured_handlers(logger: logging.Logger) -> None:
    """Detach and close handlers previously created by this module."""

    for handler in logger.handlers[:]:
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


def _mark_handler(handler: logging.Handler) -> None:
    """Mark a handler so later configuration can safely replace it."""

    setattr(handler, _HANDLER_MARKER, True)
