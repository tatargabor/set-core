"""Root logging setup for the long-running set-core processes (B-162).

The server and the engine CLI used to configure the root logger at DEBUG with no
override. Under systemd the stderr handler feeds the journal, so every DEBUG line
of a poll loop reached syslog: measured 2026-10-19, 36 706 of 37 526 journal lines
in ten minutes, gigabytes a week on a root disk that was already full.

The split this module holds:

- **stderr** (what systemd puts in the journal) is at INFO unless `SET_LOG_LEVEL`
  says otherwise;
- **a log file** (an orchestration run's `python.log`) stays at DEBUG, because
  that is the file a post-run investigation reads, and it lives with the run.

The root logger is set to the lowest handler level, so a DEBUG file still receives
DEBUG records while the stream handler drops them.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

ENV_VAR = "SET_LOG_LEVEL"
DEFAULT_STREAM_LEVEL = logging.INFO
FILE_LEVEL = logging.DEBUG
FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"

_NAMES = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def resolve_stream_level(value: Optional[str]) -> tuple[int, Optional[str]]:
    """The stderr level from the environment value, and a complaint if it was invalid.

    Returns (level, problem). `problem` is None when the value was absent or valid;
    otherwise it says what was refused, so the caller can log it once the handlers
    exist (logging it here would go nowhere).
    """
    if value is None or not value.strip():
        return DEFAULT_STREAM_LEVEL, None
    level = _NAMES.get(value.strip().upper())
    if level is None:
        return DEFAULT_STREAM_LEVEL, f"{ENV_VAR}={value!r} is not a log level; using INFO"
    return level, None


def build_handlers(log_file: Optional[str], env_value: Optional[str]) -> tuple[List[logging.Handler], Optional[str]]:
    """The handlers for a process: an optional DEBUG file handler, and stderr."""
    handlers: List[logging.Handler] = []
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(FILE_LEVEL)
        handlers.append(file_handler)
    stream_level, problem = resolve_stream_level(env_value)
    stream = logging.StreamHandler(sys.stderr)
    stream.setLevel(stream_level)
    handlers.append(stream)
    return handlers, problem


def root_level(handlers: List[logging.Handler]) -> int:
    """The lowest handler level, so no handler is starved of records it wants."""
    return min((h.level for h in handlers), default=DEFAULT_STREAM_LEVEL)


def configure(log_file: Optional[str] = None) -> None:
    """Configure the root logger. A no-op when it already has handlers, like basicConfig."""
    if logging.getLogger().handlers:
        logger.debug("logging already configured; leaving the root logger as it is")
        return
    handlers, problem = build_handlers(log_file, os.environ.get(ENV_VAR))
    logging.basicConfig(
        level=root_level(handlers),
        format=FORMAT,
        datefmt=DATEFMT,
        handlers=handlers,
    )
    if problem:
        logger.warning(problem)
    logger.debug(
        "logging configured: stream=%s file=%s",
        logging.getLevelName(handlers[-1].level),
        log_file or "-",
    )
