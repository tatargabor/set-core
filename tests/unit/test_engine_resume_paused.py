"""Test: sentinel restart auto-resumes changes parked as "paused".

Observed on craftbrew-run-20260415-0146 admin-products:
  I restarted the sentinel. engine.shutdown() set admin-products (active at
  the moment) to status=paused with the comment "so they resume on restart".
  But the dispatch loop excludes paused from ready-to-dispatch, and no
  resume_* routine picked it up — admin-products sat parked at 105K tokens
  of completed impl work until manually resumed via the dispatcher API.

Fix: `resume_paused_changes` + call it from monitor_loop startup, next to
`_cleanup_orphans` and `_resume_stalled_safe`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))

from tests.lib import test_paths as tp


def _seed_state(path: Path, changes: list[dict]) -> None:
    path.write_text(json.dumps({"status": "running", "changes": changes}))


def test_resume_paused_changes_replays_every_paused_with_worktree(tmp_path: Path):
    from set_orch.dispatcher import resume_paused_changes

    wt_a = tmp_path / "wt-a"
    wt_a.mkdir()
    state_file = tmp_path / "state.json"
    _seed_state(state_file, [
        {"name": "a", "status": "paused", "scope": "",
         "worktree_path": str(wt_a)},
        {"name": "b", "status": "running", "scope": "",
         "worktree_path": ""},  # not paused — skip
        {"name": "c", "status": "paused", "scope": "",
         "worktree_path": ""},  # paused but no worktree — skip
        {"name": "d", "status": "merged", "scope": "",
         "worktree_path": ""},  # terminal — skip
    ])

    resumed_names: list[str] = []

    def _fake_resume(_sf, name, **kwargs):
        resumed_names.append(name)
        return True

    with patch("set_orch.dispatcher.resume_change", side_effect=_fake_resume):
        count = resume_paused_changes(str(state_file))

    assert count == 1
    assert resumed_names == ["a"], (
        f"Only paused+worktree changes must resume. resumed={resumed_names}"
    )


def test_resume_paused_changes_empty_when_none_paused(tmp_path: Path):
    from set_orch.dispatcher import resume_paused_changes

    state_file = tmp_path / "state.json"
    _seed_state(state_file, [
        {"name": "x", "status": "running", "scope": "", "worktree_path": ""},
        {"name": "y", "status": "merged", "scope": "", "worktree_path": ""},
    ])
    with patch("set_orch.dispatcher.resume_change"):
        assert resume_paused_changes(str(state_file)) == 0


def test_resume_paused_integrated_with_monitor_loop_startup(tmp_path: Path):
    """Spot-check: monitor_loop calls resume_paused_changes during startup,
    right after _cleanup_orphans. We stub the loop body to abort on the
    first poll so the test doesn't hang.
    """
    from unittest.mock import MagicMock

    from set_orch import engine

    state_dir = tmp_path / "proj"
    cfg_dir = state_dir / "set" / "orchestration"
    cfg_dir.mkdir(parents=True)
    state_file = tp.state_file(state_dir)
    wt = tmp_path / "wt-paused"
    wt.mkdir()
    _seed_state(state_file, [
        {"name": "paused-one", "status": "paused", "scope": "",
         "worktree_path": str(wt)},
    ])
    (cfg_dir / "directives.json").write_text(json.dumps({"time_limit_secs": 0}))

    resumed: list[str] = []

    def _fake_resume_paused(_sf, event_bus=None, **kwargs):
        # simulate dispatcher resumed 1 change
        from set_orch.state import load_state, update_change_field
        state = load_state(_sf)
        count = 0
        for c in state.changes:
            if c.status == "paused":
                resumed.append(c.name)
                update_change_field(_sf, c.name, "status", "running")
                count += 1
        return count

    # Abort the loop before it does anything heavy — raise from _cleanup_orphans
    class _StopLoop(Exception):
        pass

    def _raise_after_paused(*_a, **_k):
        raise _StopLoop("abort after resume_paused_changes has run")

    with (
        patch.object(engine, "_cleanup_orphans", return_value=None),
        patch("set_orch.dispatcher.resume_paused_changes", side_effect=_fake_resume_paused),
        patch.object(engine, "_clear_checkpoint_state", return_value=None),
        # Abort via the very next thing in the startup chain so the loop
        # body never runs in this test.
        patch("time.sleep", side_effect=_raise_after_paused),
    ):
        try:
            engine.monitor_loop(
                str(cfg_dir / "directives.json"),
                str(state_file),
                poll_interval=1,
                event_bus=MagicMock(),
            )
        except _StopLoop:
            pass
        except Exception:
            pass

    assert resumed == ["paused-one"], (
        f"monitor_loop must auto-resume paused changes on startup. got={resumed}"
    )
