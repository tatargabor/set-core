"""Structured logging configuration for orchestration modules.

Migrated from: bin/set-orchestrate log(), log_info(), log_warn(), log_error(), log_debug()

Provides rotating file handler + stderr handler with ExtraFormatter
that appends structured key=value pairs from logging extras.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Default log format matching orchestration.log style
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(funcName)s %(message)s"

# Rotation defaults
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3

# Standard fields that are NOT extras
_STANDARD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())
_STANDARD_FIELDS.add("message")
_STANDARD_FIELDS.add("taskName")  # Python 3.12+


class ExtraFormatter(logging.Formatter):
    """Formatter that appends extra dict keys as key=value pairs.

    Example:
        logger.info("dispatch_change", extra={"change": "add-auth", "attempt": 2})
        → "2026-03-14T10:00:00 INFO set_orch.config:parse_directives dispatch_change change=add-auth attempt=2"
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_FIELDS and not k.startswith("_")
        }
        if extras:
            pairs = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base} {pairs}"
        return base


def _resolve_log_path(log_path: str | Path | None = None) -> Path:
    """Resolve the log file path.

    Priority:
    1. Explicit log_path argument
    2. SetRuntime resolution (shared runtime dir)
    3. Legacy fallback: set/orchestration/orchestration.log
    """
    if log_path is not None:
        return Path(log_path)

    try:
        from .paths import SetRuntime
        rt = SetRuntime()
        return Path(rt.orchestration_log)
    except Exception:
        pass

    # Legacy fallback
    state_file = os.environ.get("STATE_FILENAME")
    if state_file:
        return Path(state_file).parent / "orchestration.log"

    return Path("set/orchestration/orchestration.log")


def setup_logging(
    log_path: str | Path | None = None,
    file_level: int = logging.DEBUG,
    stderr_level: int = logging.WARNING,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT,
) -> logging.Logger:
    """Configure logging for all set_orch modules.

    Sets up:
    - Rotating file handler at file_level (default DEBUG)
    - Stderr handler at stderr_level (default WARNING)
    - ExtraFormatter on both handlers

    Returns the root 'set_orch' logger.
    """
    resolved_path = _resolve_log_path(log_path)

    # Ensure parent directory exists
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    # Root logger for all set_orch modules
    root_logger = logging.getLogger("set_orch")

    # Avoid duplicate handlers on repeated calls
    if root_logger.handlers:
        return root_logger

    root_logger.setLevel(logging.DEBUG)

    formatter = ExtraFormatter(LOG_FORMAT)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        str(resolved_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Stderr handler
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(stderr_level)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)

    return root_logger
