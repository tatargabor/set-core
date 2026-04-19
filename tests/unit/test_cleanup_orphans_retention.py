"""Regression test: _cleanup_orphans honors worktree_retention=keep.

User report: "lattam tegnap még mindig töröl worktreet uj phase vagy hasonlo
esetében" (even after a phase boundary/monitor restart, previous-phase
merged worktrees were still force-deleted).

Root cause: `merger.cleanup_worktree` respects the `worktree_retention`
orchestration directive and defaults to "keep", but `_cleanup_orphans` in
engine.py had an independent path that unconditionally force-removed any
worktree whose change was in status `merged` or `done`. On monitor restart
(which calls _cleanup_orphans up front) all retained worktrees of
previously-merged changes were deleted — destroying the debug surface the
user explicitly wanted to preserve.

Fix: _cleanup_orphans now consults _resolve_retention() too. keep → skip.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))

from tests.lib import test_paths as tp


def test_cleanup_orphans_skips_merged_worktree_when_retention_keep(tmp_path, monkeypatch):
    """Worktree of a merged change must survive monitor restart when
    orchestration.yaml / default retention is 'keep'."""
    import set_orch.engine as engine
    from set_orch.state import Change

    # Seed a project + a merged change with an existing worktree dir.
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_name = "project"
    wt = tmp_path / f"{project_name}-wt-foundation-setup"
    wt.mkdir()

    state_file = tp.state_file(project_dir)
    state_file.write_text(
        '{"status":"running","changes":[{"name":"foundation-setup",'
        '"status":"merged","extras":{}}]}'
    )

    # Mock git worktree list to include our merged worktree.
    wt_list_output = f"worktree {wt}\nbranch refs/heads/change/foundation-setup\n"

    def fake_run_command(cmd, *_a, **_kw):
        r = MagicMock()
        r.exit_code = 0
        r.stdout = ""
        r.stderr = ""
        if cmd[:3] == ["git", "worktree", "list"]:
            r.stdout = wt_list_output
        elif cmd[:2] == ["git", "worktree"] and cmd[2] == "remove":
            raise AssertionError(
                "retention=keep must NOT remove merged worktree, "
                f"but got: {cmd!r}"
            )
        elif cmd[:2] == ["git", "status"]:
            r.stdout = ""  # clean
        return r

    import set_orch.subprocess_utils as subproc
    monkeypatch.setattr(subproc, "run_command", fake_run_command)
    monkeypatch.setattr(engine, "_has_process_in_dir", lambda _p: False)

    # Force retention=keep regardless of host config.
    import set_orch.merger as merger_mod
    monkeypatch.setattr(merger_mod, "_resolve_retention", lambda: "keep")

    # Should not raise — the AssertionError above would fire on removal.
    engine._cleanup_orphans(str(state_file))

    # Worktree directory must still exist.
    assert wt.is_dir(), "keep retention: worktree was removed anyway"


def test_cleanup_orphans_removes_merged_worktree_when_retention_delete(tmp_path, monkeypatch):
    """When retention is explicitly 'delete-on-merge', _cleanup_orphans
    removes the merged worktree. This preserves the legacy behaviour for
    projects that opt in."""
    import set_orch.engine as engine

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    wt = tmp_path / "project-wt-foundation-setup"
    wt.mkdir()

    state_file = tp.state_file(project_dir)
    state_file.write_text(
        '{"status":"running","changes":[{"name":"foundation-setup",'
        '"status":"merged","extras":{}}]}'
    )

    wt_list_output = f"worktree {wt}\nbranch refs/heads/change/foundation-setup\n"
    removed: list[list[str]] = []

    def fake_run_command(cmd, *_a, **_kw):
        r = MagicMock()
        r.exit_code = 0
        r.stdout = ""
        r.stderr = ""
        if cmd[:3] == ["git", "worktree", "list"]:
            r.stdout = wt_list_output
        elif cmd[:3] == ["git", "worktree", "remove"]:
            removed.append(list(cmd))
        elif cmd[:3] == ["git", "worktree", "prune"]:
            # `prune` is the post-rename cleanup path; count it as a removal.
            removed.append(list(cmd))
        elif cmd[:2] == ["git", "status"]:
            r.stdout = ""
        return r

    import set_orch.subprocess_utils as subproc
    monkeypatch.setattr(subproc, "run_command", fake_run_command)
    monkeypatch.setattr(engine, "_has_process_in_dir", lambda _p: False)

    import set_orch.merger as merger_mod
    monkeypatch.setattr(merger_mod, "_resolve_retention", lambda: "delete-on-merge")

    engine._cleanup_orphans(str(state_file))

    # At least one worktree remove call must have fired.
    assert removed, "retention=delete-on-merge: expected worktree remove, none invoked"


def test_cleanup_orphans_still_removes_orphan_without_state_entry(tmp_path, monkeypatch):
    """A worktree whose name has no corresponding state entry is a true
    orphan (the change was deleted or never existed). We still clean
    those up regardless of retention — the retention rule is about
    *tracked* merged changes, not stray directories."""
    import set_orch.engine as engine

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    wt = tmp_path / "project-wt-ghost-change"
    wt.mkdir()

    state_file = tp.state_file(project_dir)
    state_file.write_text('{"status":"running","changes":[]}')

    wt_list_output = f"worktree {wt}\nbranch refs/heads/change/ghost-change\n"
    removed: list[list[str]] = []

    def fake_run_command(cmd, *_a, **_kw):
        r = MagicMock()
        r.exit_code = 0
        r.stdout = ""
        r.stderr = ""
        if cmd[:3] == ["git", "worktree", "list"]:
            r.stdout = wt_list_output
        elif cmd[:3] == ["git", "worktree", "remove"]:
            removed.append(list(cmd))
        elif cmd[:3] == ["git", "worktree", "prune"]:
            # `prune` is the post-rename cleanup path; count it as a removal.
            removed.append(list(cmd))
        elif cmd[:2] == ["git", "status"]:
            r.stdout = ""
        return r

    import set_orch.subprocess_utils as subproc
    monkeypatch.setattr(subproc, "run_command", fake_run_command)
    monkeypatch.setattr(engine, "_has_process_in_dir", lambda _p: False)

    import set_orch.merger as merger_mod
    monkeypatch.setattr(merger_mod, "_resolve_retention", lambda: "keep")

    engine._cleanup_orphans(str(state_file))

    assert removed, "orphan (no state entry) must be removed regardless of retention"
