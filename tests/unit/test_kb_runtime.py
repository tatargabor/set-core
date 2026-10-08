"""Runtime probe: FTS5 present → ok; absent → a loud error, no fallback."""

from __future__ import annotations

import sqlite3

import pytest

from set_kb import runtime
from set_kb.runtime import KbRuntimeError, probe


def test_probe_succeeds_and_reports_sqlite_version():
    info = probe()
    assert info["sqlite"] == sqlite3.sqlite_version
    assert info["sqlite"]  # a version string, not a placeholder


def test_probe_failure_names_fts5_and_remediation(monkeypatch):
    class NoFts5Conn:
        def execute(self, sql, *a):
            if "USING fts5" in sql:
                raise sqlite3.OperationalError("no such module: fts5")
            raise sqlite3.OperationalError("unexpected probe statement")

        def close(self):
            pass

    monkeypatch.setattr(runtime.sqlite3, "connect", lambda *a, **k: NoFts5Conn())
    with pytest.raises(KbRuntimeError) as e:
        probe()
    msg = str(e.value)
    assert "FTS5" in msg, "the error must name the missing piece"
    assert "uv python install" in msg, "the error must carry the remediation"
    assert "no such module: fts5" in msg, "the underlying cause travels with the message"
    monkeypatch.undo()
    assert probe()["sqlite"]  # the real runtime still probes clean afterwards


def test_probe_uses_memory_only(monkeypatch):
    """A failing probe must not create anything on disk (AC: no index is created)."""
    opened = []

    real_connect = sqlite3.connect

    def spy_connect(path, *a, **k):
        opened.append(path)
        return real_connect(path, *a, **k)

    monkeypatch.setattr(runtime.sqlite3, "connect", spy_connect)
    probe()
    monkeypatch.undo()
    assert opened == [":memory:"]
