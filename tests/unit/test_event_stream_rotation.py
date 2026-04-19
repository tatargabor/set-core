"""Tests for Section 1 — event stream rotation on replan and sentinel stop.

Covers:
  - 1.4 Rotation creates cycleN file, new empty live file, preserves content
  - 1.5 Rotation failure logs WARNING and replan continues
  - AC-1, AC-2, AC-3
"""

from __future__ import annotations

import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import (
    _next_cycle_index,
    _rotate_event_streams,
)
from set_orch.state import init_state, load_state, save_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _setup_project(tmp_path):
    """Create a project dir, write a plan + state, return useful paths."""
    proj = tmp_path / "proj"
    proj.mkdir()
    plan_path = str(proj / "plan.json")
    state_path = str(proj / "state.json")
    plan = {
        "plan_version": 1,
        "brief_hash": "h",
        "plan_phase": "initial",
        "plan_method": "api",
        "input_path": "docs/spec.md",
        "changes": [
            {"name": "foundation", "scope": "s", "complexity": "M", "phase": 1},
        ],
    }
    with open(plan_path, "w") as fh:
        json.dump(plan, fh)
    init_state(plan_path, state_path,
               spec_path="docs/spec.md", project_path=str(proj))
    return proj, plan_path, state_path


def _write_live_streams(proj, *, n_events=3, n_state=2):
    """Populate live event streams under proj/orchestration/."""
    events = proj / "orchestration-events.jsonl"
    state_events = proj / "orchestration-state-events.jsonl"
    with open(events, "w") as fh:
        for i in range(n_events):
            fh.write(json.dumps({"type": "EVT", "i": i}) + "\n")
    with open(state_events, "w") as fh:
        for i in range(n_state):
            fh.write(json.dumps({"type": "STATE_CHANGE", "i": i}) + "\n")
    return str(events), str(state_events)


# ---------------------------------------------------------------------------
# _next_cycle_index
# ---------------------------------------------------------------------------


def test_next_cycle_index_starts_at_one(tmp_path):
    assert _next_cycle_index(str(tmp_path)) == 1


def test_next_cycle_index_picks_next_after_max(tmp_path):
    for n in (1, 2, 5):
        (tmp_path / f"orchestration-events-cycle{n}.jsonl").write_text("")
    (tmp_path / "orchestration-state-events-cycle3.jsonl").write_text("")
    assert _next_cycle_index(str(tmp_path)) == 6


# ---------------------------------------------------------------------------
# 1.4 / AC-1 — rotation creates cycle file, fresh live, preserves content
# ---------------------------------------------------------------------------


def test_rotation_seals_live_stream_into_cycle_file(tmp_path):
    proj, plan_path, state_path = _setup_project(tmp_path)
    events_live, state_events_live = _write_live_streams(proj)

    cycle = _rotate_event_streams(state_path, reason="replan")
    assert cycle == 1

    # Live files exist but are empty.
    assert os.path.exists(events_live)
    assert os.path.getsize(events_live) == 0
    assert os.path.getsize(state_events_live) == 0

    # Rotated copies exist with header + original content.
    rotated = proj / "orchestration-events-cycle1.jsonl"
    state_rotated = proj / "orchestration-state-events-cycle1.jsonl"
    assert rotated.is_file() and state_rotated.is_file()

    lines = rotated.read_text().splitlines()
    assert len(lines) == 4  # 1 header + 3 originals
    header = json.loads(lines[0])
    assert header["type"] == "CYCLE_HEADER"
    assert header["cycle"] == 1
    assert header["reason"] == "replan"
    assert header["spec_lineage_id"] == "docs/spec.md"
    assert header["sentinel_session_id"] is not None
    assert header["plan_version"] == 1

    # Subsequent lines preserve original payload order.
    payload = [json.loads(l) for l in lines[1:]]
    assert [p["i"] for p in payload] == [0, 1, 2]


def test_rotation_with_only_one_stream_present(tmp_path):
    proj, _, state_path = _setup_project(tmp_path)
    only_events = proj / "orchestration-events.jsonl"
    only_events.write_text(json.dumps({"type": "EVT"}) + "\n")
    cycle = _rotate_event_streams(state_path, reason="replan")
    assert cycle == 1
    assert (proj / "orchestration-events-cycle1.jsonl").is_file()
    # No state-events sibling created when nothing to rotate.
    assert not (proj / "orchestration-state-events-cycle1.jsonl").is_file()


def test_rotation_skips_when_streams_empty(tmp_path):
    proj, _, state_path = _setup_project(tmp_path)
    cycle = _rotate_event_streams(state_path, reason="replan")
    assert cycle is None
    assert not list(proj.glob("orchestration-events-cycle*.jsonl"))


def test_rotation_assigns_monotonic_cycle_ids(tmp_path):
    proj, _, state_path = _setup_project(tmp_path)
    _write_live_streams(proj, n_events=1, n_state=0)
    assert _rotate_event_streams(state_path) == 1
    _write_live_streams(proj, n_events=1, n_state=0)
    assert _rotate_event_streams(state_path) == 2
    _write_live_streams(proj, n_events=1, n_state=0)
    assert _rotate_event_streams(state_path) == 3


# ---------------------------------------------------------------------------
# 1.5 / AC-3 — rotation failure logs WARNING and replan continues
# ---------------------------------------------------------------------------


def test_rotation_failure_is_logged_and_does_not_raise(tmp_path, monkeypatch, caplog):
    proj, _, state_path = _setup_project(tmp_path)
    _write_live_streams(proj)

    real_rename = os.rename
    def boom(src, dst):
        if "orchestration-events-cycle" in dst:
            raise OSError("simulated disk full")
        return real_rename(src, dst)
    monkeypatch.setattr(os, "rename", boom)

    with caplog.at_level(logging.WARNING, logger="set_orch.engine"):
        # Should NOT raise — rotation is best-effort.
        cycle = _rotate_event_streams(state_path, reason="replan")
    assert cycle == 1  # cycle id still allocated
    assert any("simulated disk full" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Header tagging when state lineage is missing
# ---------------------------------------------------------------------------


def test_header_lineage_is_null_when_state_corrupt(tmp_path, caplog):
    proj = tmp_path / "proj"
    proj.mkdir()
    state_path = str(proj / "state.json")
    # Write an unreadable state.json — corrupted JSON.
    with open(state_path, "w") as fh:
        fh.write("{ this is not json")
    events = proj / "orchestration-events.jsonl"
    events.write_text(json.dumps({"type": "EVT"}) + "\n")

    cycle = _rotate_event_streams(state_path, reason="replan")
    assert cycle == 1
    rotated = proj / "orchestration-events-cycle1.jsonl"
    header = json.loads(rotated.read_text().splitlines()[0])
    assert header["spec_lineage_id"] is None
    assert header["sentinel_session_id"] is None
