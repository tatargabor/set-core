"""Tests for the events-api resolver chain (observability-event-file-unification)."""

import json
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.orchestration import (
    _list_rotated_event_files,
    _read_jsonl_events,
    _resolve_events_file,
    get_events,
)


def _write_jsonl(path: Path, events: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


# ─── _resolve_events_file resolver chain ──────────────────────────────


def test_resolver_picks_live_when_both_present(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "orchestration-events.jsonl", [{"type": "STATE_CHANGE"}])
    _write_jsonl(tmp_path / "orchestration-state-events.jsonl", [{"type": "DIGEST"}])
    resolved = _resolve_events_file(tmp_path)
    assert resolved is not None
    assert resolved.name == "orchestration-events.jsonl"


def test_resolver_falls_back_to_narrow(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "orchestration-state-events.jsonl", [{"type": "DIGEST"}])
    resolved = _resolve_events_file(tmp_path)
    assert resolved is not None
    assert resolved.name == "orchestration-state-events.jsonl"


def test_resolver_falls_back_to_legacy_nested_live(tmp_path: Path) -> None:
    nested = tmp_path / "set" / "orchestration" / "orchestration-events.jsonl"
    _write_jsonl(nested, [{"type": "STATE_CHANGE"}])
    resolved = _resolve_events_file(tmp_path)
    assert resolved is not None
    assert resolved == nested


def test_resolver_returns_none_when_no_files(tmp_path: Path) -> None:
    assert _resolve_events_file(tmp_path) is None


# ─── get_events endpoint ──────────────────────────────────────────────


def test_get_events_returns_live_when_both_present(tmp_path: Path, monkeypatch) -> None:
    _write_jsonl(
        tmp_path / "orchestration-events.jsonl",
        [{"type": "STATE_CHANGE", "n": i} for i in range(5)],
    )
    _write_jsonl(
        tmp_path / "orchestration-state-events.jsonl",
        [{"type": "DIGEST", "n": 99}],
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _: tmp_path
    )
    result = get_events("any-project", type=None, limit=500)
    assert len(result["events"]) == 5
    assert all(e.get("type") == "STATE_CHANGE" for e in result["events"])


def test_get_events_empty_when_no_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _: tmp_path
    )
    result = get_events("any-project", type=None, limit=500)
    assert result == {"events": []}


def test_get_events_limit_returns_last_n(tmp_path: Path, monkeypatch) -> None:
    _write_jsonl(
        tmp_path / "orchestration-events.jsonl",
        [{"type": "X", "n": i} for i in range(100)],
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _: tmp_path
    )
    result = get_events("p", type=None, limit=10)
    ns = [e["n"] for e in result["events"]]
    assert ns == list(range(90, 100))


def test_get_events_type_filter(tmp_path: Path, monkeypatch) -> None:
    events = []
    for i in range(50):
        events.append({"type": "OTHER", "n": i})
    for i in range(5):
        events.append({"type": "STATE_CHANGE", "n": 100 + i})
    _write_jsonl(tmp_path / "orchestration-events.jsonl", events)
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _: tmp_path
    )
    result = get_events("p", type="STATE_CHANGE", limit=500)
    assert len(result["events"]) == 5
    assert all(e["type"] == "STATE_CHANGE" for e in result["events"])


# ─── Rotation-aware fill ──────────────────────────────────────────────


def test_get_events_rotation_fills_to_limit(tmp_path: Path, monkeypatch) -> None:
    # Live tail has 5 events; one rotated cycle has 30 events.
    _write_jsonl(
        tmp_path / "orchestration-events.jsonl",
        [{"type": "X", "src": "live", "n": i} for i in range(5)],
    )
    _write_jsonl(
        tmp_path / "orchestration-events-cycle1.jsonl",
        [{"type": "X", "src": "cycle1", "n": 100 + i} for i in range(30)],
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _: tmp_path
    )
    result = get_events("p", type=None, limit=20)
    assert len(result["events"]) == 20
    # Last 5 are from live; first 15 are the latest rotated-cycle events
    assert [e["src"] for e in result["events"][-5:]] == ["live"] * 5
    assert all(e["src"] == "cycle1" for e in result["events"][:15])


def test_get_events_no_rotation_when_live_sufficient(tmp_path: Path, monkeypatch) -> None:
    _write_jsonl(
        tmp_path / "orchestration-events.jsonl",
        [{"type": "X", "n": i} for i in range(1000)],
    )
    _write_jsonl(
        tmp_path / "orchestration-events-cycle1.jsonl",
        [{"type": "X", "src": "cycle1", "n": 99999}],
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _: tmp_path
    )
    result = get_events("p", type=None, limit=500)
    assert len(result["events"]) == 500
    # All from the live tail (no cycle1 events leaked in)
    assert all(e.get("src") != "cycle1" for e in result["events"])


def test_list_rotated_event_files_skips_non_live_resolver(tmp_path: Path) -> None:
    # When the resolved file is the narrow stream, rotation lookup returns
    # empty (rotation siblings only apply to the live stream).
    narrow = tmp_path / "orchestration-state-events.jsonl"
    narrow.touch()
    rotated = _list_rotated_event_files(narrow)
    assert rotated == []


# ─── State reconstruct resolver chain ─────────────────────────────────


def test_reconstruct_prefers_live_stream(tmp_path: Path) -> None:
    from set_orch.state import (
        Change,
        OrchestratorState,
        reconstruct_state_from_events,
        save_state,
    )

    state_path = tmp_path / "orchestration-state.json"
    state = OrchestratorState(
        plan_version=1,
        status="running",
        changes=[Change(name="foo", scope="x")],
    )
    save_state(state, str(state_path))

    # Live stream has the STATE_CHANGE event; narrow stream has only DIGEST.
    _write_jsonl(
        tmp_path / "orchestration-events.jsonl",
        [
            {"type": "STATE_CHANGE", "change": "foo",
             "data": {"from": "pending", "to": "merged"}},
        ],
    )
    _write_jsonl(
        tmp_path / "orchestration-state-events.jsonl",
        [{"type": "DIGEST_COMPLETE"}],
    )

    ok = reconstruct_state_from_events(str(state_path))
    assert ok
    from set_orch.state import load_state as _ls
    rebuilt = _ls(str(state_path))
    foo = next(c for c in rebuilt.changes if c.name == "foo")
    assert foo.status == "merged"


def test_reconstruct_narrow_fallback(tmp_path: Path) -> None:
    from set_orch.state import (
        Change,
        OrchestratorState,
        reconstruct_state_from_events,
        save_state,
    )

    state_path = tmp_path / "orchestration-state.json"
    save_state(
        OrchestratorState(plan_version=1, status="running",
                          changes=[Change(name="foo", scope="x")]),
        str(state_path),
    )

    # Only narrow stream present, with one STATE_CHANGE event.
    _write_jsonl(
        tmp_path / "orchestration-state-events.jsonl",
        [{"type": "STATE_CHANGE", "change": "foo",
          "data": {"from": "pending", "to": "merged"}}],
    )

    ok = reconstruct_state_from_events(str(state_path))
    assert ok
    from set_orch.state import load_state as _ls
    rebuilt = _ls(str(state_path))
    assert next(c for c in rebuilt.changes if c.name == "foo").status == "merged"


def test_reconstruct_returns_false_when_no_events(tmp_path: Path) -> None:
    from set_orch.state import (
        Change,
        OrchestratorState,
        reconstruct_state_from_events,
        save_state,
    )
    state_path = tmp_path / "orchestration-state.json"
    save_state(
        OrchestratorState(plan_version=1, status="running",
                          changes=[Change(name="foo", scope="x")]),
        str(state_path),
    )
    assert reconstruct_state_from_events(str(state_path)) is False
