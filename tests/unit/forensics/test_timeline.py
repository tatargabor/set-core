from __future__ import annotations

import pytest

from set_orch.forensics.resolver import resolve_run
from set_orch.forensics.timeline import (
    AmbiguousSessionPrefix,
    session_timeline,
    to_json,
    to_markdown,
)


def _tu(tu_id, name, inp=None):
    return {"type": "tool_use", "id": tu_id, "name": name, "input": inp or {}}


def _tr(tu_id, content, is_error=False):
    b = {"type": "tool_result", "tool_use_id": tu_id, "content": content}
    if is_error:
        b["is_error"] = True
    return b


def _a(ts, blocks, sr="tool_use"):
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"role": "assistant", "stop_reason": sr, "content": blocks},
    }


def _u(ts, blocks):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": blocks}}


def _resolve(run_layout):
    return resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )


def test_session_resolved_by_prefix(run_layout, write_session):
    records = [
        _a("2026-04-20T12:00:00.000Z", [_tu("tu_1", "Read", {"file_path": "/x"})]),
        _u("2026-04-20T12:00:01.000Z", [_tr("tu_1", "content")]),
        _a("2026-04-20T12:00:02.000Z", [{"type": "text", "text": "done"}], sr="end_turn"),
    ]
    write_session(run_layout["main_session_dir"], "abcdef12-1234-5678-9abc-deadbeefcafe", records)

    resolved = _resolve(run_layout)
    timeline = session_timeline(resolved, "abcdef")
    assert timeline.session_uuid.startswith("abcdef")
    assert any(e.event_type == "tool_use" and e.tool_name == "Read" for e in timeline.entries)
    assert any(e.event_type == "stop" and e.summary == "stop_reason=end_turn" for e in timeline.entries)


def test_ambiguous_prefix_raises_with_candidates(run_layout, write_session):
    write_session(
        run_layout["main_session_dir"],
        "aaaa1111-0000-0000-0000-000000000000",
        [_a("2026-04-20T12:00:00.000Z", [], sr="end_turn")],
    )
    write_session(
        run_layout["worktree_dirs"]["auth-setup"],
        "aaaa2222-0000-0000-0000-000000000000",
        [_a("2026-04-20T12:00:00.000Z", [], sr="end_turn")],
    )

    resolved = _resolve(run_layout)
    with pytest.raises(AmbiguousSessionPrefix) as exc_info:
        session_timeline(resolved, "aaaa")
    assert len(exc_info.value.candidates) == 2


def test_errors_only_filters_clean_events(run_layout, write_session):
    records = [
        _a("2026-04-20T12:00:00.000Z", [_tu("tu_ok", "Read", {"file_path": "/x"})]),
        _u("2026-04-20T12:00:01.000Z", [_tr("tu_ok", "ok content")]),
        _a("2026-04-20T12:00:02.000Z", [_tu("tu_bad", "Bash", {"command": "nope"})]),
        _u("2026-04-20T12:00:03.000Z", [_tr("tu_bad", "boom", is_error=True)]),
        _a("2026-04-20T12:00:04.000Z", [{"type": "text", "text": "done"}], sr="end_turn"),
    ]
    write_session(run_layout["main_session_dir"], "sess-errors-test-0000-0000-00000000", records)

    resolved = _resolve(run_layout)
    timeline = session_timeline(resolved, "sess-errors", errors_only=True)
    outcomes = {e.outcome for e in timeline.entries}
    assert outcomes == {"error"}
    # Only the failing tool_result survives (plus optionally stops with non-clean reasons).
    assert any(e.event_type == "tool_result" for e in timeline.entries)


def test_tool_filter_matches_case_insensitive(run_layout, write_session):
    records = [
        _a("t0", [_tu("tu_r", "Read", {})]),
        _u("t1", [_tr("tu_r", "x")]),
        _a("t2", [_tu("tu_b", "Bash", {"command": "ls"})]),
        _u("t3", [_tr("tu_b", "listing")]),
        _a("t4", [], sr="end_turn"),
    ]
    write_session(run_layout["main_session_dir"], "toolfilt-0000-0000-0000-000000000000", records)

    resolved = _resolve(run_layout)
    timeline = session_timeline(resolved, "toolfilt", tool="bash")
    tools = {e.tool_name for e in timeline.entries if e.tool_name}
    assert tools == {"Bash"}

    md = to_markdown(timeline)
    assert "Bash" in md
    js = to_json(timeline)
    assert js["session_uuid"].startswith("toolfilt")
