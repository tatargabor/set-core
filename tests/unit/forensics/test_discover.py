from __future__ import annotations

import json

from set_orch.forensics.discover import build_discover_payload, to_markdown
from set_orch.forensics.resolver import resolve_run


def _resolve(run_layout):
    return resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )


def test_discover_markdown_lists_main_plus_worktrees(run_layout, write_session):
    write_session(run_layout["main_session_dir"], "m1", [{"type": "user", "message": {"content": "hi"}}])
    write_session(
        run_layout["worktree_dirs"]["auth-setup"],
        "a1",
        [{"type": "user", "message": {"content": "hi"}}],
    )
    write_session(
        run_layout["worktree_dirs"]["cart-and-session"],
        "c1",
        [{"type": "user", "message": {"content": "hi"}}],
    )

    resolved = _resolve(run_layout)
    payload = build_discover_payload(resolved)
    md = to_markdown(payload)

    # Must show main plus two worktrees as rows.
    assert md.count("| `main`") == 1
    assert "| `auth-setup`" in md
    assert "| `cart-and-session`" in md
    # Orchestration artifacts section with (found)/(missing) indicators.
    assert "orchestration-events.jsonl" in md
    assert "(missing)" in md or "(found)" in md


def test_discover_json_has_required_keys(run_layout, write_session):
    write_session(run_layout["main_session_dir"], "m1", [{"type": "user", "message": {"content": "hi"}}])
    resolved = _resolve(run_layout)
    payload = build_discover_payload(resolved)
    # Payload must be JSON-serialisable.
    dumped = json.dumps(payload, default=str)
    parsed = json.loads(dumped)
    assert {"run_id", "main", "worktrees", "orchestration"} <= set(parsed.keys())
