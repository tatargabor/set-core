from __future__ import annotations

from set_orch.forensics.grep import DEFAULT_LIMIT, grep_content, to_json, to_markdown
from set_orch.forensics.resolver import resolve_run


def _u(ts, blocks):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": blocks}}


def _a(ts, blocks, sr="end_turn"):
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"role": "assistant", "stop_reason": sr, "content": blocks},
    }


def _resolve(run_layout):
    return resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )


def test_grep_emits_content_text_not_jsonl_keys(run_layout, write_session):
    records = [
        _a("t0", [{"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {"command": "npm test"}}]),
        _u(
            "t1",
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu_1",
                    "content": "EACCES: permission denied\nnpm failed",
                    "is_error": True,
                }
            ],
        ),
    ]
    write_session(run_layout["main_session_dir"], "grep-s1-0000-0000-0000-000000000000", records)

    resolved = _resolve(run_layout)
    outcome = grep_content(resolved, "EACCES")
    assert outcome.total_matches == 1
    assert len(outcome.matches) == 1
    match = outcome.matches[0]
    assert "EACCES" in match.snippet
    # Structural jsonl keys must NOT leak into the snippet.
    assert '"type":"tool_result"' not in match.snippet
    assert '"tool_use_id":"tu_1"' not in match.snippet
    assert "tool_use_id" not in match.snippet


def test_grep_limit_cap_enforced(run_layout, write_session):
    # Create 100 matches in one session.
    big_text = "\n".join(["MATCHME line %d" % i for i in range(100)])
    records = [
        _a("t0", [{"type": "text", "text": big_text}], sr="end_turn"),
    ]
    write_session(run_layout["main_session_dir"], "grep-big-0000-0000-0000-000000000000", records)

    resolved = _resolve(run_layout)
    outcome = grep_content(resolved, "MATCHME")
    assert outcome.total_matches == 100
    assert len(outcome.matches) == DEFAULT_LIMIT == 50

    md = to_markdown(outcome)
    assert "50 more matches suppressed" in md

    js = to_json(outcome)
    assert js["total_matches"] == 100
    assert js["suppressed"] == 50


def test_grep_case_insensitive(run_layout, write_session):
    records = [_a("t0", [{"type": "text", "text": "Failed to Connect"}], sr="end_turn")]
    write_session(run_layout["main_session_dir"], "grep-ci-0000-0000-0000-000000000000", records)

    resolved = _resolve(run_layout)
    # Case-sensitive: no match.
    assert grep_content(resolved, "failed").total_matches == 0
    # Case-insensitive: match.
    assert grep_content(resolved, "failed", case_insensitive=True).total_matches == 1


def test_grep_tool_filter(run_layout, write_session):
    records = [
        _a("t0", [{"type": "tool_use", "id": "tu_b", "name": "Bash", "input": {"command": "echo boom"}}]),
        _u(
            "t1",
            [{"type": "tool_result", "tool_use_id": "tu_b", "content": "boom from bash"}],
        ),
        _a("t2", [{"type": "tool_use", "id": "tu_r", "name": "Read", "input": {"file_path": "/etc/boom"}}]),
        _u(
            "t3",
            [{"type": "tool_result", "tool_use_id": "tu_r", "content": "boom from read"}],
        ),
    ]
    write_session(run_layout["main_session_dir"], "grep-tool-0000-0000-0000-000000000000", records)

    resolved = _resolve(run_layout)
    bash_only = grep_content(resolved, "boom", tool="Bash")
    # "boom" appears in both Bash input (command) and Bash tool_result → 2 matches.
    # It must NOT pick up the Read tool_use/result.
    assert all(m.tool_name == "Bash" for m in bash_only.matches)
    assert bash_only.total_matches == 2
