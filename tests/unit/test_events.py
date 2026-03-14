"""Tests for wt_orch.events."""

import json
import time
from pathlib import Path

import pytest

from wt_orch.events import EventBus, _resolve_log_path


# ─── EventBus.emit ──────────────────────────────────────────────────


class TestEmit:
    def test_basic_emit(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("STATE_CHANGE", change="add-auth", data={"status": "running"})

        lines = log.read_text().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "STATE_CHANGE"
        assert event["change"] == "add-auth"
        assert event["data"] == {"status": "running"}
        assert "ts" in event

    def test_emit_without_change(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("ORCHESTRATOR_START", data={"version": "1.0"})

        event = json.loads(log.read_text().strip())
        assert event["type"] == "ORCHESTRATOR_START"
        assert "change" not in event
        assert event["data"] == {"version": "1.0"}

    def test_emit_without_data(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("HEARTBEAT")

        event = json.loads(log.read_text().strip())
        assert event["type"] == "HEARTBEAT"
        assert event["data"] == {}

    def test_emit_multiple(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("A")
        bus.emit("B")
        bus.emit("C")

        lines = log.read_text().splitlines()
        assert len(lines) == 3

    def test_emit_disabled(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log, enabled=False)
        bus.emit("STATE_CHANGE", data={"x": 1})

        assert not log.exists()

    def test_emit_creates_parent_dirs(self, tmp_path):
        log = tmp_path / "sub" / "dir" / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("TEST")

        assert log.exists()

    def test_jsonl_compact_format(self, tmp_path):
        """Verify compact JSON separators (no spaces) for bash compatibility."""
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("STATE_CHANGE", change="x", data={"key": "val"})

        line = log.read_text().strip()
        # No spaces after : or ,
        assert ": " not in line
        assert ", " not in line
        # Valid JSON
        event = json.loads(line)
        assert event["data"]["key"] == "val"

    def test_emit_enable_disable(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.enabled = False
        bus.emit("A")
        assert not log.exists()

        bus.enabled = True
        bus.emit("B")
        assert log.exists()
        assert len(log.read_text().splitlines()) == 1


# ─── EventBus.rotate_log ────────────────────────────────────────────


class TestRotateLog:
    def test_no_rotation_under_threshold(self, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text("small\n")
        bus = EventBus(log_path=log, max_size=1000)
        bus.rotate_log()

        assert log.read_text() == "small\n"
        archives = list(tmp_path.glob("events-*.jsonl"))
        assert len(archives) == 0

    def test_rotation_over_threshold(self, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text("x" * 2000)
        bus = EventBus(log_path=log, max_size=1000)
        bus.rotate_log()

        # Original file should be empty (touched)
        assert log.exists()
        assert log.stat().st_size == 0
        # Archive should exist
        archives = list(tmp_path.glob("events-*.jsonl"))
        assert len(archives) == 1

    def test_rotation_keeps_max_archives(self, tmp_path):
        log = tmp_path / "events.jsonl"
        # Create 5 pre-existing archives
        for i in range(5):
            archive = tmp_path / f"events-2025010{i}120000.jsonl"
            archive.write_text(f"archive {i}")

        log.write_text("x" * 2000)
        bus = EventBus(log_path=log, max_size=1000)
        bus.rotate_log()

        # 3 kept + 1 new = should be 3 total (DEFAULT_MAX_ARCHIVES=3)
        archives = list(tmp_path.glob("events-*.jsonl"))
        assert len(archives) == 3

    def test_rotation_nonexistent_file(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        # Should not raise
        bus.rotate_log()

    def test_periodic_rotation_check(self, tmp_path):
        """Verify rotation check fires every ROTATION_CHECK_INTERVAL emissions."""
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log, max_size=100)

        # Emit 100 events (ROTATION_CHECK_INTERVAL) — file will grow large
        for i in range(100):
            bus.emit("TICK", data={"i": i})

        # After 100 emissions, rotation should have been triggered
        archives = list(tmp_path.glob("events-*.jsonl"))
        assert len(archives) >= 1


# ─── EventBus.query ──────────────────────────────────────────────────


class TestQuery:
    def _populate(self, bus, events):
        for e in events:
            bus.emit(e.get("type", "TEST"), change=e.get("change", ""), data=e.get("data", {}))

    def test_query_all(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        self._populate(bus, [{"type": "A"}, {"type": "B"}, {"type": "C"}])

        results = bus.query()
        assert len(results) == 3

    def test_query_by_type(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        self._populate(bus, [{"type": "A"}, {"type": "B"}, {"type": "A"}])

        results = bus.query(event_type="A")
        assert len(results) == 2
        assert all(e["type"] == "A" for e in results)

    def test_query_by_change(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        self._populate(bus, [
            {"type": "X", "change": "ch1"},
            {"type": "X", "change": "ch2"},
            {"type": "X", "change": "ch1"},
        ])

        results = bus.query(change="ch1")
        assert len(results) == 2

    def test_query_last_n(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        self._populate(bus, [{"type": "A"}, {"type": "B"}, {"type": "C"}, {"type": "D"}])

        results = bus.query(last_n=2)
        assert len(results) == 2
        assert results[0]["type"] == "C"
        assert results[1]["type"] == "D"

    def test_query_by_since(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.emit("OLD", data={"i": 0})
        # All events have current timestamp, so filtering with a future ts returns nothing
        results = bus.query(since="2099-01-01T00:00:00")
        assert len(results) == 0

        # Filtering with a past ts returns everything
        results = bus.query(since="2000-01-01T00:00:00")
        assert len(results) == 1

    def test_query_combined_filters(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        self._populate(bus, [
            {"type": "STATE", "change": "ch1"},
            {"type": "STATE", "change": "ch2"},
            {"type": "LOG", "change": "ch1"},
        ])

        results = bus.query(event_type="STATE", change="ch1")
        assert len(results) == 1

    def test_query_empty_log(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        assert bus.query() == []

    def test_query_nonexistent_file(self, tmp_path):
        bus = EventBus(log_path=tmp_path / "nope.jsonl")
        assert bus.query() == []

    def test_query_malformed_lines(self, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text('{"type":"A","data":{}}\nnot json\n{"type":"B","data":{}}\n')
        bus = EventBus(log_path=log)
        results = bus.query()
        assert len(results) == 2


# ─── EventBus.format_table ───────────────────────────────────────────


class TestFormatTable:
    def test_empty_events(self):
        bus = EventBus(enabled=False)
        assert bus.format_table([]) == "No events found."

    def test_table_output(self):
        bus = EventBus(enabled=False)
        events = [
            {"ts": "2025-01-01T00:00:00+00:00", "type": "STATE_CHANGE", "change": "add-auth", "data": {"status": "ok"}},
        ]
        table = bus.format_table(events)
        assert "STATE_CHANGE" in table
        assert "add-auth" in table
        assert "2025-01-01" in table


# ─── EventBus.subscribe ─────────────────────────────────────────────


class TestSubscribe:
    def test_subscribe_specific_type(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        received = []
        bus.subscribe("STATE_CHANGE", lambda e: received.append(e))

        bus.emit("STATE_CHANGE", data={"x": 1})
        bus.emit("OTHER", data={"y": 2})

        assert len(received) == 1
        assert received[0]["data"] == {"x": 1}

    def test_subscribe_wildcard(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        received = []
        bus.subscribe("*", lambda e: received.append(e))

        bus.emit("A")
        bus.emit("B")

        assert len(received) == 2

    def test_subscribe_multiple_handlers(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        r1, r2 = [], []
        bus.subscribe("X", lambda e: r1.append(e))
        bus.subscribe("X", lambda e: r2.append(e))

        bus.emit("X")

        assert len(r1) == 1
        assert len(r2) == 1

    def test_handler_error_doesnt_break_emit(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.subscribe("X", lambda e: 1 / 0)  # will raise ZeroDivisionError

        # Should not raise
        bus.emit("X", data={"safe": True})
        assert log.exists()

    def test_wildcard_handler_error_doesnt_break(self, tmp_path):
        log = tmp_path / "events.jsonl"
        bus = EventBus(log_path=log)
        bus.subscribe("*", lambda e: 1 / 0)

        bus.emit("Y")
        assert log.exists()


# ─── _resolve_log_path ───────────────────────────────────────────────


class TestResolveLogPath:
    def test_from_state_filename(self, monkeypatch):
        monkeypatch.setenv("STATE_FILENAME", "/tmp/myproject-state.json")
        path = _resolve_log_path()
        assert path == Path("/tmp/myproject-events.jsonl")

    def test_default_without_env(self, monkeypatch):
        monkeypatch.delenv("STATE_FILENAME", raising=False)
        path = _resolve_log_path()
        assert path == Path("orchestration-events.jsonl")

    def test_state_filename_complex(self, monkeypatch):
        monkeypatch.setenv("STATE_FILENAME", "/var/data/sales-raketa-state.json")
        path = _resolve_log_path()
        assert path == Path("/var/data/sales-raketa-events.jsonl")
