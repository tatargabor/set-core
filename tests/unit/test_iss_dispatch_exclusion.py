"""Tests for the ISS/engine dispatch mutual exclusion.

When a circuit breaker fires it creates BOTH (a) a `fix-iss-*` change
in `state.changes` and (b) an `Issue` in `.set/issues/registry.json`
linked to that change name. The ISS pipeline (IssueManager) runs
`/opsx:ff` + `/opsx:apply` sequentially in the set-core directory to
investigate and fix. If the engine's worktree dispatcher ALSO picks
up the same `fix-iss-*` change on its next poll, two agents modify
the same openspec change concurrently and produce git conflicts.

The dispatcher must therefore consult the IssueRegistry and skip any
pending change whose name matches an Issue currently in an active
(non-NEW, non-terminal) state.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.dispatcher import _iss_owned_change_names  # noqa: E402


def _write_registry(project: Path, issues: list[dict]) -> None:
    d = project / ".set" / "issues"
    d.mkdir(parents=True, exist_ok=True)
    (d / "registry.json").write_text(json.dumps({"issues": issues, "groups": []}))


def test_iss_owned_returns_empty_when_no_registry(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    assert _iss_owned_change_names(str(state_file)) == set()


def test_iss_owned_skips_new_and_terminal_states(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    _write_registry(tmp_path, [
        {"id": "ISS-001", "state": "new", "change_name": "fix-iss-001-x"},
        {"id": "ISS-002", "state": "resolved", "change_name": "fix-iss-002-y"},
        {"id": "ISS-003", "state": "cancelled", "change_name": "fix-iss-003-z"},
        {"id": "ISS-004", "state": "dismissed", "change_name": "fix-iss-004-w"},
    ])
    # NEW has not been claimed yet (investigation not spawned), terminal
    # states are done — none of these should block the engine dispatch.
    assert _iss_owned_change_names(str(state_file)) == set()


def test_iss_owned_claims_active_pipeline_changes(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    _write_registry(tmp_path, [
        {"id": "ISS-001", "state": "investigating",
         "change_name": "fix-iss-001-catalog"},
        {"id": "ISS-002", "state": "diagnosed",
         "change_name": "fix-iss-002-stories"},
        {"id": "ISS-003", "state": "fixing",
         "change_name": "fix-iss-003-checkout"},
        {"id": "ISS-004", "state": "awaiting_approval",
         "change_name": "fix-iss-004-promo"},
    ])
    owned = _iss_owned_change_names(str(state_file))
    assert owned == {
        "fix-iss-001-catalog", "fix-iss-002-stories",
        "fix-iss-003-checkout", "fix-iss-004-promo",
    }


def test_iss_owned_ignores_issues_without_change_name(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    _write_registry(tmp_path, [
        {"id": "ISS-001", "state": "investigating", "change_name": ""},
        {"id": "ISS-002", "state": "fixing"},
    ])
    assert _iss_owned_change_names(str(state_file)) == set()


def test_dispatcher_skips_iss_owned_change(tmp_path, monkeypatch):
    """End-to-end: a fix-iss change that the ISS is investigating must
    NOT be dispatched by the engine even if dependencies are satisfied.
    """
    from set_orch.state import Change, OrchestratorState, save_state
    from set_orch.dispatcher import dispatch_ready_changes

    state_file = str(tmp_path / "state.json")
    state = OrchestratorState(status="running", changes=[
        Change(name="foundation", scope="x", status="merged",
               complexity="S", phase=1),
        Change(name="fix-iss-001-foundation", scope="x", status="pending",
               complexity="S", phase=2, depends_on=["foundation"]),
    ])
    state.extras["current_phase"] = 2
    save_state(state, state_file)

    # ISS claims ownership of fix-iss-001-foundation.
    _write_registry(tmp_path, [
        {"id": "ISS-001", "state": "investigating",
         "change_name": "fix-iss-001-foundation"},
    ])

    # Stub the actual worktree dispatch so the test doesn't spawn agents.
    called: list[str] = []
    import set_orch.dispatcher as _d
    monkeypatch.setattr(_d, "dispatch_change", lambda *a, **k: called.append(a[1]) or True)

    dispatched = dispatch_ready_changes(state_file, max_parallel=2)

    assert dispatched == 0
    assert called == []


def test_dispatcher_dispatches_fix_iss_when_iss_is_terminal(tmp_path, monkeypatch):
    """Negative control: when the ISS finished (resolved/dismissed), or
    when no registry exists at all, the engine picks up the fix-iss
    change normally. This keeps the mutual-exclusion gate OFF for
    projects that do not use the ISS pipeline.
    """
    from set_orch.state import Change, OrchestratorState, save_state
    from set_orch.dispatcher import dispatch_ready_changes

    state_file = str(tmp_path / "state.json")
    state = OrchestratorState(status="running", changes=[
        Change(name="foundation", scope="x", status="merged",
               complexity="S", phase=1),
        Change(name="fix-iss-002-foundation", scope="x", status="pending",
               complexity="S", phase=2, depends_on=["foundation"]),
    ])
    state.extras["current_phase"] = 2
    save_state(state, state_file)

    _write_registry(tmp_path, [
        {"id": "ISS-002", "state": "resolved",
         "change_name": "fix-iss-002-foundation"},
    ])

    called: list[str] = []
    import set_orch.dispatcher as _d
    monkeypatch.setattr(_d, "dispatch_change", lambda *a, **k: called.append(a[1]) or True)

    dispatch_ready_changes(state_file, max_parallel=2)

    assert called == ["fix-iss-002-foundation"]
