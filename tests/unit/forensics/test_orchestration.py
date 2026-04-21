from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.forensics.orchestration import (
    OrchestrationDirMissing,
    orchestration_summary,
    to_json,
    to_markdown,
)
from set_orch.forensics.resolver import resolve_run


def _write(path: Path, records):
    with path.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _resolve(run_layout):
    return resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )


def test_dispatch_counts_reflect_events(run_layout):
    events = run_layout["orchestration_dir"] / "orchestration-events.jsonl"
    _write(
        events,
        [
            {"event": "DISPATCH", "timestamp": "t0", "change": "auth-setup"},
            {"event": "DISPATCH", "timestamp": "t1", "change": "auth-setup"},
            {"event": "DISPATCH", "timestamp": "t2", "change": "auth-setup"},
            {"event": "DISPATCH", "timestamp": "t0", "change": "cart-and-session"},
        ],
    )
    # Also need state events file (empty is fine).
    (run_layout["orchestration_dir"] / "orchestration-state-events.jsonl").write_text("")

    # Need at least one session dir to resolve.
    (run_layout["main_session_dir"] / "x.jsonl").write_text("")

    resolved = _resolve(run_layout)
    summary = orchestration_summary(resolved)
    rows = {r.change: r for r in summary.dispatch_rows}
    assert rows["auth-setup"].num_dispatches == 3
    assert rows["cart-and-session"].num_dispatches == 1


def test_gate_outcomes_grouped_by_gate_name(run_layout):
    events = run_layout["orchestration_dir"] / "orchestration-events.jsonl"
    _write(
        events,
        [
            {"event": "VERIFY_GATE", "timestamp": "t0", "change": "x", "gate": "review", "verdict": "pass"},
            {"event": "VERIFY_GATE", "timestamp": "t1", "change": "x", "gate": "review", "verdict": "pass"},
            {"event": "VERIFY_GATE", "timestamp": "t2", "change": "x", "gate": "review", "verdict": "pass"},
            {"event": "VERIFY_GATE", "timestamp": "t3", "change": "x", "gate": "review", "verdict": "fail"},
            {"event": "VERIFY_GATE", "timestamp": "t4", "change": "x", "gate": "review", "verdict": "fail"},
            {"event": "VERIFY_GATE", "timestamp": "t0", "change": "x", "gate": "build", "verdict": "pass"},
            {"event": "VERIFY_GATE", "timestamp": "t1", "change": "x", "gate": "build", "verdict": "pass"},
        ],
    )
    (run_layout["orchestration_dir"] / "orchestration-state-events.jsonl").write_text("")
    (run_layout["main_session_dir"] / "x.jsonl").write_text("")

    resolved = _resolve(run_layout)
    summary = orchestration_summary(resolved)
    assert summary.gate_outcomes["review"] == {"pass": 3, "fail": 2}
    assert summary.gate_outcomes["build"] == {"pass": 2}


def test_missing_orch_dir_raises(run_layout):
    # Remove the orchestration dir.
    import shutil
    shutil.rmtree(run_layout["orchestration_dir"])
    # Keep a session dir so resolve_run succeeds.
    (run_layout["main_session_dir"] / "x.jsonl").write_text("")

    resolved = resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )
    with pytest.raises(OrchestrationDirMissing):
        orchestration_summary(resolved)


def test_state_transitions_ordered(run_layout):
    (run_layout["orchestration_dir"] / "orchestration-events.jsonl").write_text("")
    state_path = run_layout["orchestration_dir"] / "orchestration-state-events.jsonl"
    _write(
        state_path,
        [
            {"timestamp": "t2", "change": "x", "field": "status", "old": "dispatched", "new": "stalled"},
            {"timestamp": "t1", "change": "x", "field": "status", "old": "ready", "new": "dispatched"},
        ],
    )
    (run_layout["main_session_dir"] / "x.jsonl").write_text("")

    resolved = _resolve(run_layout)
    summary = orchestration_summary(resolved)
    assert [t.timestamp for t in summary.state_transitions] == ["t1", "t2"]

    md = to_markdown(summary)
    assert "State transitions" in md
    js = to_json(summary)
    assert len(js["state_transitions"]) == 2
