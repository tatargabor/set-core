"""
Tests for GUI logging infrastructure.
"""

import logging
import sys
import tempfile
from pathlib import Path

import pytest


def _expected_log_path():
    """Return the expected log path matching production logic."""
    if sys.platform == "win32":
        return Path(tempfile.gettempdir()) / "set-control.log"
    return Path("/tmp") / "set-control.log"


def test_setup_logging_creates_handler():
    """setup_logging should add a RotatingFileHandler to the set-control logger."""
    from gui.logging_setup import setup_logging

    root = logging.getLogger("set-control")
    # Clear any existing handlers from prior test runs
    root.handlers.clear()

    setup_logging()

    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1

    handler = root.handlers[0]
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3

    # Cleanup
    root.handlers.clear()


def test_setup_logging_writes_startup_message():
    """setup_logging should write a startup message to the log file."""
    from gui.logging_setup import setup_logging

    root = logging.getLogger("set-control")
    root.handlers.clear()

    log_path = _expected_log_path()
    setup_logging()

    assert log_path.exists()
    content = log_path.read_text()
    assert "GUI starting" in content

    root.handlers.clear()


def test_setup_logging_no_duplicate_handlers():
    """Calling setup_logging twice should not add duplicate handlers."""
    from gui.logging_setup import setup_logging

    root = logging.getLogger("set-control")
    root.handlers.clear()

    setup_logging()
    setup_logging()

    assert len(root.handlers) == 1
    root.handlers.clear()


def test_log_format():
    """Log messages should follow the expected format."""
    from gui.logging_setup import setup_logging

    root = logging.getLogger("set-control")
    root.handlers.clear()
    setup_logging()

    log_path = _expected_log_path()

    # Write a test message
    test_logger = logging.getLogger("set-control.test")
    test_logger.info("test_message key=value")

    content = log_path.read_text()
    # Check format: date, time, level, module:function, message
    lines = content.strip().split("\n")
    last_line = lines[-1]
    assert "INFO" in last_line
    assert "set-control.test" in last_line
    assert "test_message key=value" in last_line

    root.handlers.clear()


def test_log_exceptions_decorator():
    """log_exceptions decorator should catch and log exceptions."""
    from gui.logging_setup import log_exceptions, setup_logging

    root = logging.getLogger("set-control")
    root.handlers.clear()
    setup_logging()

    @log_exceptions
    def failing_function():
        raise ValueError("test error 12345")

    with pytest.raises(ValueError, match="test error 12345"):
        failing_function()

    log_path = _expected_log_path()
    content = log_path.read_text()
    assert "test error 12345" in content
    assert "Exception in failing_function" in content

    root.handlers.clear()


def test_child_logger_hierarchy():
    """Child loggers should inherit the root handler."""
    from gui.logging_setup import setup_logging

    root = logging.getLogger("set-control")
    root.handlers.clear()
    setup_logging()

    child = logging.getLogger("set-control.handlers")
    # Child should not have its own handlers but propagate to root
    assert len(child.handlers) == 0
    assert child.parent is root

    log_path = _expected_log_path()
    child.info("child_test_message")

    content = log_path.read_text()
    assert "child_test_message" in content
    assert "set-control.handlers" in content

    root.handlers.clear()
