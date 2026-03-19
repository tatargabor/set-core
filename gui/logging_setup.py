"""
Logging setup for the Control Center GUI.

Configures a rotating file logger at the platform temp directory.
All GUI modules use child loggers under the 'set-control' root.
"""

import logging
import sys
import tempfile
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging():
    """Initialize GUI logging with rotating file handler.

    Log file: /tmp/set-control.log (macOS/Linux) or %TEMP%/set-control.log (Windows)
    Rotation: 5 MB max, 3 backup files.
    """
    if sys.platform == "win32":
        log_path = Path(tempfile.gettempdir()) / "set-control.log"
    else:
        log_path = Path("/tmp") / "set-control.log"

    root_logger = logging.getLogger("set-control")
    root_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on restart
    if root_logger.handlers:
        return

    handler = RotatingFileHandler(
        str(log_path),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s:%(funcName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    root_logger.info(
        "GUI starting — Python %s, %s",
        sys.version.split()[0],
        sys.platform,
    )


def log_exceptions(func):
    """Decorator that logs exceptions in Qt signal handlers.

    Qt swallows exceptions in signal-connected slots. This decorator
    catches, logs, and re-raises them so they appear in the log file.
    """
    logger = logging.getLogger("set-control.handlers")

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Exception in %s", func.__name__)
            raise

    return wrapper


def safe_slot(func):
    """Decorator for worker signal handler slots.

    Like log_exceptions, but suppresses the exception instead of re-raising.
    This prevents a single bad worker result from crashing the UI — the slot
    logs the error and the UI continues with stale data.
    """
    logger = logging.getLogger("set-control.slots")

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Exception in slot %s", func.__name__)

    return wrapper
