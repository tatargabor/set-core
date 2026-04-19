"""Tests for Section 4 — readers concatenate rotated event files.

Covers:
  - 4.3 Activity timeline reads cycleN files in cycle order before live
  - 4.4 LLM-calls endpoint returns events from both cycle files
  - AC-8, AC-9
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from tests.lib import test_paths as tp

from set_orch.api.activity import _load_events
from set_orch.api.orchestration import _read_llm_call_events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Point SetRuntime at an empty tmp dir so the test does not pick up the
    host machine's sentinel events from the real ~/.local/share/set-core/."""
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


@pytest.fixture
def project_with_cycles(tmp_path):
    """Project with two rotated cycles + a live event file."""
    proj = tmp_path / "proj"
    proj.mkdir()

    def _write_cycle(name: str, n: int, events: list[dict]) -> None:
        path = proj / f"{name}-cycle{n}.jsonl"
        with open(path, "w") as fh:
            # CYCLE_HEADER mirrors what the rotator writes.
            fh.write(json.dumps({
                "type": "CYCLE_HEADER",
                "ts": f"2026-01-0{n}T00:00:00+00:00",
                "cycle": n,
                "spec_lineage_id": "docs/spec.md",
                "sentinel_session_id": f"session-{n}",
                "plan_version": n,
            }) + "\n")
            for ev in events:
                fh.write(json.dumps(ev) + "\n")

    # Cycle 1 events (older)
    _write_cycle("orchestration-events", 1, [
        {"type": "DISPATCH", "ts": "2026-01-01T10:00:00+00:00", "change": "foundation"},
        {"type": "STATE_CHANGE", "ts": "2026-01-01T10:05:00+00:00", "change": "foundation",
         "data": {"from": "pending", "to": "running"}},
        {"type": "LLM_CALL", "ts": "2026-01-01T10:06:00+00:00", "change": "foundation",
         "data": {"purpose": "review", "model": "opus", "input_tokens": 100,
                  "output_tokens": 50, "duration_ms": 200}},
    ])
    # Cycle 2 events (later)
    _write_cycle("orchestration-events", 2, [
        {"type": "DISPATCH", "ts": "2026-01-02T10:00:00+00:00", "change": "catalog"},
        {"type": "LLM_CALL", "ts": "2026-01-02T10:01:00+00:00", "change": "catalog",
         "data": {"purpose": "spec_verify", "model": "opus", "input_tokens": 80,
                  "output_tokens": 40, "duration_ms": 150}},
    ])
    # Live events (current cycle)
    with open(tp.events_file(proj), "w") as fh:
        fh.write(json.dumps({
            "type": "LLM_CALL", "ts": "2026-01-03T10:00:00+00:00", "change": "shipping",
            "data": {"purpose": "review", "model": "opus", "input_tokens": 50,
                     "output_tokens": 25, "duration_ms": 100},
        }) + "\n")

    return proj


# ---------------------------------------------------------------------------
# 4.3 / AC-8 — activity timeline reads all cycles in chronological order
# ---------------------------------------------------------------------------


def test_activity_timeline_reads_all_cycles(project_with_cycles):
    events = _load_events(project_with_cycles, from_ts=None, to_ts=None)
    # CYCLE_HEADER lines are filtered out — only real events remain.
    types = [e["type"] for e in events]
    assert "CYCLE_HEADER" not in types
    # Cycle 1 events come first (DISPATCH foundation), cycle 2 next
    # (DISPATCH catalog), live last (LLM_CALL shipping).
    timestamps = [e.get("ts", "") for e in events]
    assert timestamps == sorted(timestamps)
    changes = [e.get("change") for e in events if "change" in e]
    assert "foundation" in changes
    assert "catalog" in changes
    assert "shipping" in changes


def test_activity_timeline_handles_double_digit_cycles(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    for n in (1, 2, 9, 10, 11):
        with open(proj / f"orchestration-events-cycle{n}.jsonl", "w") as fh:
            fh.write(json.dumps({
                "type": "DISPATCH",
                "ts": f"2026-01-{n:02d}T00:00:00+00:00",
                "change": f"change-{n}",
            }) + "\n")
    events = _load_events(proj, from_ts=None, to_ts=None)
    # Numeric cycle order means cycle10 comes after cycle9, not after cycle1.
    cycle_order = [e["change"] for e in events]
    assert cycle_order == ["change-1", "change-2", "change-9", "change-10", "change-11"]


# ---------------------------------------------------------------------------
# 4.4 / AC-9 — llm-calls endpoint includes rotated cycles, deduplicated
# ---------------------------------------------------------------------------


def test_llm_calls_endpoint_includes_rotated_events(project_with_cycles):
    calls: list[dict] = []
    _read_llm_call_events(project_with_cycles, calls)
    purposes = [c["purpose_raw"] for c in calls]
    # All three LLM_CALL events show up (one per cycle file + live).
    assert "review" in purposes
    assert "spec_verify" in purposes
    # Two "review" entries were emitted at different timestamps; both
    # should appear (dedup works on (ts, change, purpose_raw) tuple).
    review_calls = [c for c in calls if c["purpose_raw"] == "review"]
    assert len(review_calls) == 2


def test_llm_calls_dedup_drops_duplicate_emissions(tmp_path):
    """When the same LLM_CALL is emitted by both event_bus and engine,
    the dedup key (ts, change, purpose) should keep just one copy."""
    proj = tmp_path / "proj"
    proj.mkdir()
    duplicate_event = json.dumps({
        "type": "LLM_CALL",
        "ts": "2026-01-01T10:00:00+00:00",
        "change": "foundation",
        "data": {"purpose": "review", "model": "opus",
                 "input_tokens": 100, "output_tokens": 50, "duration_ms": 200},
    }) + "\n"
    # Both files contain the same event — the engine sometimes writes
    # to two files due to historic dual-emission.
    with open(tp.events_file(proj), "w") as fh:
        fh.write(duplicate_event)
    with open(tp.state_events_file(proj), "w") as fh:
        fh.write(duplicate_event)
    calls: list[dict] = []
    _read_llm_call_events(proj, calls)
    assert len(calls) == 1
