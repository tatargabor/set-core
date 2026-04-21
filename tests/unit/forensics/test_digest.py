from __future__ import annotations

from set_orch.forensics.digest import (
    SIGNAL_BASH_EXIT,
    SIGNAL_STOP_ANOMALY,
    SIGNAL_TOOL_ERROR,
    digest_run,
    to_json,
    to_markdown,
)
from set_orch.forensics.resolver import resolve_run


def _tool_use(tu_id, name, inp=None):
    return {"type": "tool_use", "id": tu_id, "name": name, "input": inp or {}}


def _tool_result(tu_id, content, is_error=False):
    block = {"type": "tool_result", "tool_use_id": tu_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block


def _assistant_record(ts, blocks, stop_reason="tool_use"):
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {
            "role": "assistant",
            "stop_reason": stop_reason,
            "content": blocks,
        },
    }


def _user_record(ts, blocks):
    return {
        "type": "user",
        "timestamp": ts,
        "message": {"role": "user", "content": blocks},
    }


def _resolve(run_layout):
    return resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )


def test_bash_exit_code_surfaces_in_digest(run_layout, write_session):
    records = [
        _assistant_record(
            "2026-04-20T12:00:00.000Z",
            [_tool_use("tu_1", "Bash", {"command": "npm install"})],
        ),
        _user_record(
            "2026-04-20T12:00:05.000Z",
            [_tool_result("tu_1", "exit code: 1\nnpm install failed")],
        ),
        _assistant_record(
            "2026-04-20T12:00:06.000Z",
            [{"type": "text", "text": "done"}],
            stop_reason="end_turn",
        ),
    ]
    write_session(run_layout["worktree_dirs"]["auth-setup"], "sess-aaa", records)

    resolved = _resolve(run_layout)
    result = digest_run(resolved)

    bash_groups = [g for g in result.groups if g.signal_type == SIGNAL_BASH_EXIT]
    assert len(bash_groups) == 1
    g = bash_groups[0]
    assert g.change == "auth-setup"
    assert g.tool_name == "Bash"
    assert g.count == 1
    assert "exit code: 1" in g.snippet


def test_max_tokens_stop_reason_counted(run_layout, write_session):
    records = [
        _assistant_record(
            "2026-04-20T12:01:00.000Z",
            [{"type": "text", "text": "long output..."}],
            stop_reason="max_tokens",
        ),
    ]
    write_session(run_layout["worktree_dirs"]["cart-and-session"], "sess-bbb", records)

    resolved = _resolve(run_layout)
    result = digest_run(resolved)

    anomalies = [g for g in result.groups if g.signal_type == SIGNAL_STOP_ANOMALY]
    assert len(anomalies) == 1
    assert anomalies[0].change == "cart-and-session"
    assert anomalies[0].session_uuid == "sess-bbb"

    # Crash suspect also fires because the last stop_reason is not clean.
    assert any(s["session_uuid"] == "sess-bbb" for s in result.crash_suspect_sessions)


def test_clean_session_produces_no_noise(run_layout, write_session):
    records = [
        _assistant_record(
            "2026-04-20T12:02:00.000Z",
            [_tool_use("tu_1", "Read", {"file_path": "/x"})],
        ),
        _user_record(
            "2026-04-20T12:02:01.000Z",
            [_tool_result("tu_1", "file contents")],
        ),
        _assistant_record(
            "2026-04-20T12:02:02.000Z",
            [{"type": "text", "text": "ok"}],
            stop_reason="end_turn",
        ),
    ]
    write_session(run_layout["main_session_dir"], "sess-clean", records)

    resolved = _resolve(run_layout)
    result = digest_run(resolved)

    assert result.groups == []
    assert result.crash_suspect_sessions == []
    assert result.sessions_scanned == 1


def test_grouping_across_worktree_dirs(run_layout, write_session):
    # Two worktrees each with one failing session.
    for change in ("auth-setup", "cart-and-session"):
        write_session(
            run_layout["worktree_dirs"][change],
            f"sess-{change}",
            [
                _assistant_record(
                    "2026-04-20T12:03:00.000Z",
                    [_tool_use("tu_x", "Bash", {"command": "fail"})],
                ),
                _user_record(
                    "2026-04-20T12:03:01.000Z",
                    [_tool_result("tu_x", "boom", is_error=True)],
                ),
            ],
        )

    resolved = _resolve(run_layout)
    result = digest_run(resolved)

    changes = {g.change for g in result.groups}
    assert changes == {"auth-setup", "cart-and-session"}

    error_groups = [g for g in result.groups if g.signal_type == SIGNAL_TOOL_ERROR]
    assert len(error_groups) == 2
    for g in error_groups:
        assert g.tool_name == "Bash"

    md = to_markdown(result)
    assert "## Summary" in md
    assert "## Errors by change" in md
    assert "auth-setup" in md
    assert "cart-and-session" in md

    js = to_json(result)
    assert js["sessions_scanned"] == 2
    assert js["total_signals"] >= 2
