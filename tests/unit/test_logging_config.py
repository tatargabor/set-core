"""Tests for set_orch.logging_config."""

import logging
import os
import tempfile
from pathlib import Path

import pytest

from set_orch.logging_config import ExtraFormatter, _resolve_log_path, setup_logging


class TestExtraFormatter:
    def test_basic_message(self):
        formatter = ExtraFormatter("%(message)s")
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        assert formatter.format(record) == "hello"

    def test_with_extras(self):
        formatter = ExtraFormatter("%(message)s")
        record = logging.LogRecord("test", logging.INFO, "", 0, "dispatch", (), None)
        record.change = "add-auth"
        record.attempt = 2
        result = formatter.format(record)
        assert "dispatch" in result
        assert "change=add-auth" in result
        assert "attempt=2" in result

    def test_no_extras_no_suffix(self):
        formatter = ExtraFormatter("%(message)s")
        record = logging.LogRecord("test", logging.INFO, "", 0, "plain", (), None)
        assert formatter.format(record) == "plain"

    def test_ignores_private_fields(self):
        formatter = ExtraFormatter("%(message)s")
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        record._internal = "hidden"
        record.visible = "shown"
        result = formatter.format(record)
        assert "_internal" not in result
        assert "visible=shown" in result


class TestResolveLogPath:
    def test_explicit_path(self):
        result = _resolve_log_path("/custom/path.log")
        assert result == Path("/custom/path.log")

    def test_from_state_filename(self, monkeypatch):
        monkeypatch.setenv("STATE_FILENAME", "/project/wt/orchestration/orchestration-state.json")
        result = _resolve_log_path()
        assert result == Path("/project/wt/orchestration/orchestration.log")

    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("STATE_FILENAME", raising=False)
        result = _resolve_log_path()
        assert result == Path("wt/orchestration/orchestration.log")

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("STATE_FILENAME", "/env/state.json")
        result = _resolve_log_path("/explicit/log.log")
        assert result == Path("/explicit/log.log")


class TestSetupLogging:
    def test_creates_logger_with_handlers(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_path=log_file)
        assert logger.name == "set_orch"
        assert len(logger.handlers) == 2  # file + stderr
        # Cleanup
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()

    def test_creates_parent_dirs(self, tmp_path):
        log_file = tmp_path / "deep" / "nested" / "test.log"
        logger = setup_logging(log_path=log_file)
        assert log_file.parent.exists()
        # Cleanup
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()

    def test_no_duplicate_handlers(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger1 = setup_logging(log_path=log_file)
        logger2 = setup_logging(log_path=log_file)
        assert logger1 is logger2
        assert len(logger1.handlers) == 2
        # Cleanup
        for h in logger1.handlers[:]:
            logger1.removeHandler(h)
            h.close()

    def test_file_handler_writes(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_path=log_file, stderr_level=logging.CRITICAL)
        child = logging.getLogger("set_orch.test_module")
        child.info("test message", extra={"key": "value"})
        # Flush
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text()
        assert "test message" in content
        assert "key=value" in content
        # Cleanup
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()

    def test_module_logger_naming(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_path=log_file, stderr_level=logging.CRITICAL)
        child = logging.getLogger("set_orch.config")
        assert child.name == "set_orch.config"
        child.warning("config warning")
        for h in logger.handlers:
            h.flush()
        content = log_file.read_text()
        assert "set_orch.config" in content
        # Cleanup
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()
