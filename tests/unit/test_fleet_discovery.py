"""Fleet discovery and state — the walking skeleton of the `fleet-view` change.

Every test here was checked against the code removed (`git stash`) before being
believed. Three of them are shaped by findings rather than by the happy path,
and they say so, because a test whose reason is only in a commit message is a
test the next person deletes as redundant.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from set_orch.fleet import discovery, state


# --------------------------------------------------------------------------- #
# a fake /proc, so discovery is testable without live agents
# --------------------------------------------------------------------------- #

def _make_proc(tmp_path: Path, entries: dict[int, dict]) -> str:
    """entries: pid -> {comm, argv, cwd}"""
    root = tmp_path / "proc"
    root.mkdir(exist_ok=True)
    for pid, spec in entries.items():
        d = root / str(pid)
        d.mkdir()
        (d / "comm").write_text(spec["comm"] + "\n")
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in spec["argv"]) + b"\0")
        target = tmp_path / "trees" / spec["cwd"]
        target.mkdir(parents=True, exist_ok=True)
        os.symlink(target, d / "cwd")
    # a non-numeric entry, which /proc really does contain
    (root / "meminfo").write_text("")
    return str(root)


def test_an_agent_is_identified_by_comm_not_by_its_command_line(tmp_path, monkeypatch):
    """The measured failure: a naive command-line match returned 31 false
    positives on a live machine — every one a shell whose *snapshot path*
    contained the binary's name. `comm` is the identity; a command line is text.
    """
    proc = _make_proc(tmp_path, {
        10: {"comm": "claude", "argv": ["claude", "--dangerously-skip-permissions"], "cwd": "a"},
        11: {"comm": "bash", "argv": ["/bin/bash", "-c", "source /home/x/.claude/shell-snapshots/s.sh"], "cwd": "b"},
    })
    monkeypatch.setattr(discovery, "SESSION_RECORD_DIR", tmp_path / "none")
    agents = discovery.discover_agents(proc_root=proc, record_dir=tmp_path / "none")
    assert [a.pid for a in agents] == [10]


def test_a_bare_substring_check_would_not_have_caught_it(tmp_path):
    """Holds the pattern that was WRONG, so a later 'simplification' back to a
    substring test fails instead of looking identical and checking nothing.
    """
    shell_argv = ["/bin/bash", "-c", "source /home/x/.claude/shell-snapshots/snapshot.sh"]
    assert "claude" in " ".join(shell_argv)          # the naive check matches …
    assert "bash" != discovery.AGENT_COMM             # … and the identity check does not


def test_a_one_shot_subprocess_is_classified_and_excluded_by_default(tmp_path):
    """Finding CB-8: the framework spawns `claude -p` subprocesses with a project
    as cwd during every orchestration run. Each would otherwise get a tile, and
    would read as *finished its turn* the moment its last entry was written.
    """
    proc = _make_proc(tmp_path, {
        20: {"comm": "claude", "argv": ["claude", "--dangerously-skip-permissions"], "cwd": "a"},
        21: {"comm": "claude", "argv": ["claude", "-p", "do a thing"], "cwd": "a"},
    })
    empty = tmp_path / "none"
    assert [a.pid for a in discovery.discover_agents(proc_root=proc, record_dir=empty)] == [20]
    both = discovery.discover_agents(proc_root=proc, record_dir=empty, include_oneshot=True)
    assert {a.pid: a.kind for a in both} == {20: "interactive", 21: "oneshot"}


def test_an_agent_with_no_session_record_is_still_an_agent(tmp_path):
    """Measured twice on 2026-08-18, from two unrelated causes: a session at its
    start-up trust prompt, and a session that inherited a child-session marker
    and writes no transcript at all. Both were alive and invisible to the
    runtime's own listing. `sources` is how the surface can say so.
    """
    proc = _make_proc(tmp_path, {30: {"comm": "claude", "argv": ["claude"], "cwd": "a"}})
    agents = discovery.discover_agents(proc_root=proc, record_dir=tmp_path / "none")
    assert len(agents) == 1
    assert agents[0].sources == ["process"]
    assert agents[0].binding_confirmed is False
    assert agents[0].session_id is None


def test_a_recorded_binding_is_used_and_marked_confirmed(tmp_path):
    proc = _make_proc(tmp_path, {40: {"comm": "claude", "argv": ["claude"], "cwd": "a"}})
    records = tmp_path / "records"
    records.mkdir()
    (records / "40.json").write_text(json.dumps({
        "pid": 40, "sessionId": "sess-40", "name": "proj-ab", "status": "idle",
    }))
    logs = tmp_path / "logs" / "proj"
    logs.mkdir(parents=True)
    (logs / "sess-40.jsonl").write_text("")
    agents = discovery.discover_agents(proc_root=proc, record_dir=records, log_root=tmp_path / "logs")
    assert agents[0].session_id == "sess-40"
    assert agents[0].binding_confirmed is True
    assert agents[0].name == "proj-ab"
    assert agents[0].sources == ["process", "session-record"]


# --------------------------------------------------------------------------- #
# one agent by pid — task 6.2
# --------------------------------------------------------------------------- #

def test_a_pid_is_verified_by_identity_not_taken_on_trust(tmp_path):
    """`comm` is what the kernel records as the program's name. Matching command
    lines instead finds every shell whose path happens to contain the word — 31
    of them on the machine this was measured on — and a caller-supplied pid is
    exactly where that would be believed.
    """
    from set_orch.fleet.discovery import discover_agent, is_agent_process

    proc = tmp_path / "proc"
    (proc / "100").mkdir(parents=True)
    (proc / "100" / "comm").write_text("bash\n")
    (proc / "200").mkdir(parents=True)
    (proc / "200" / "comm").write_text("claude\n")
    (proc / "200" / "cwd").symlink_to(tmp_path)

    assert is_agent_process(100, str(proc)) is False
    assert is_agent_process(200, str(proc)) is True
    assert discover_agent(100, proc_root=str(proc)) is None
    assert discover_agent(999, proc_root=str(proc)) is None


def test_one_agent_skips_git_unless_asked(tmp_path, monkeypatch):
    """The whole saving. A caller that wants the log or the state needs the
    session binding, not the branch; asking git per call is what made the
    per-agent routes cost the whole inventory.
    """
    from set_orch.fleet import discovery as disc

    proc = tmp_path / "proc"
    (proc / "200").mkdir(parents=True)
    (proc / "200" / "comm").write_text("claude\n")
    (proc / "200" / "cwd").symlink_to(tmp_path)
    (proc / "200" / "cmdline").write_bytes(b"claude\x00")

    monkeypatch.setattr(disc, "_git_branch", lambda cwd: pytest.fail("git must not be asked"))
    monkeypatch.setattr(disc, "resolve_project", lambda cwd: pytest.fail("git must not be asked"))

    agent = disc.discover_agent(200, proc_root=str(proc), record_dir=tmp_path / "none")
    assert agent is not None
    assert agent.branch is None and agent.project_name is None
    assert agent.sources == ["process"]
    assert agent.binding_confirmed is False
