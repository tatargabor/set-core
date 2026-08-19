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


# --------------------------------------------------------------------------- #
# lineage — task 2.5
# --------------------------------------------------------------------------- #

def _proc_entry(proc, pid, comm, ppid):
    d = proc / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "comm").write_text(comm + "\n")
    # The real format, parentheses and all — a comm may contain spaces and
    # brackets, which is exactly what breaks a naive whitespace split.
    (d / "stat").write_text(f"{pid} ({comm}) S {ppid} 0 0 0 -1 0 0 0 0 0 0 0\n")
    return d


def test_the_walk_climbs_through_non_agent_processes(tmp_path):
    """An agent that runs `claude` from its own shell is two links away, not one.
    Stopping at the immediate parent would report no lineage for the commonest
    way one agent starts another by hand.
    """
    from set_orch.fleet.discovery import parent_seat

    proc = tmp_path / "proc"
    _proc_entry(proc, 100, "claude", 1)       # the ancestor
    _proc_entry(proc, 200, "bash", 100)       # a shell in between
    _proc_entry(proc, 300, "claude", 200)     # the descendant

    found = parent_seat(300, proc_root=str(proc), record_dir=tmp_path / "none")
    assert found is not None
    assert found["source"] == "ancestry"
    assert found["pid_without_seat"] == 100, "a pid with no record must not lose the relation"


def test_the_stat_parse_survives_a_comm_with_spaces_and_brackets(tmp_path):
    """`/proc/<pid>/stat` puts `comm` in parentheses in field 2, and a comm may
    contain both spaces and parentheses. Splitting the line on whitespace reads
    the wrong field for exactly those processes — and they are the ones a walk
    passes through.
    """
    from set_orch.fleet.discovery import _ppid

    proc = tmp_path / "proc"
    d = proc / "500"
    d.mkdir(parents=True)
    (d / "stat").write_text("500 (weird (name) here) S 42 0 0 0 -1 0 0 0 0 0 0 0\n")
    assert _ppid(500, str(proc)) == 42


def test_no_agent_above_reports_nothing_rather_than_guessing(tmp_path):
    """MEASURED 2026-08-19 and this is the ORDINARY case, not the edge: 0 of 23
    live agents had an agent ancestor, and an agent started from the fleet screen
    has the owner — a plain python process — as its parent, with systemd above
    that. Reporting the nearest process instead would put a lineage edge on the
    screen between an agent and a service.
    """
    from set_orch.fleet.discovery import parent_seat

    proc = tmp_path / "proc"
    _proc_entry(proc, 10, "systemd", 1)
    _proc_entry(proc, 20, "python3", 10)
    _proc_entry(proc, 30, "claude", 20)
    assert parent_seat(30, proc_root=str(proc), record_dir=tmp_path / "none") is None


def test_a_recorded_origin_outranks_ancestry_and_says_which_it_is(monkeypatch):
    """The two answer different questions and can disagree, so the surface is
    told which kind it got. The recorded one wins because it is the only one that
    can answer for a framework-started agent at all — but it is a CLAIM the
    framework did not verify, and marking it as measured would be a false value.
    """
    from set_orch.api import fleet as fleet_api

    class _A:
        pid, name, project_name, project_root, cwd = 7, "n", "p", "/r", "/r"
        branch = session_id = record = None
        binding_confirmed = True
        sources = ["process"]
        sources_missing = ["session-record", "registry"]
        kind = "interactive"

    # The REAL dataclass. A hand-listed stand-in is a second copy of
    # `AgentState`, and this one drifted the moment the dataclass gained a
    # field: the test failed with `AttributeError` on a product that was
    # correct, which accuses the code of a fault the fixture caused.
    from set_orch.fleet.state import AgentState

    def _S():
        return AgentState(state="quiet", last_movement_age=1.0)

    monkeypatch.setattr(fleet_api, "parent_seat", lambda pid: {"seat": "x", "source": "ancestry"})
    payload = fleet_api._agent_payload(_A(), _S(), {7: {"label": "l", "requested_by": "set-core-12"}})
    assert payload["parent"] == {"seat": "set-core-12", "source": "recorded"}


def test_the_sources_that_LACKED_an_agent_are_named(tmp_path):
    """Task 2.8's second half, and it is not derivable from `sources` alone: a
    shorter list is only meaningful against the set that was consulted. Without
    this, "known to one source" and "known to one of three" render identically —
    and the second is the one worth looking at.

    ⚠ Measured 2026-08-19: **0 of 23** live agents were known from the process
    alone; all had a session record. The path is real (two causes were measured
    on 2026-08-18 — a session at its trust prompt, and a child session that
    writes no transcript) but no live instance exists to point at, so this drives
    it from a fixture rather than claiming the live case was seen.
    """
    from set_orch.fleet.discovery import CONSULTED_SOURCES, Agent

    lonely = Agent(pid=1, cwd="/x", sources=["process"])
    assert lonely.sources_missing == ["session-record", "registry"]

    known = Agent(pid=2, cwd="/x", sources=list(CONSULTED_SOURCES))
    assert known.sources_missing == []


def test_the_missing_list_is_the_complement_of_a_STATED_set():
    """Derived from a named constant rather than from whatever a caller passed.
    An absence measured against an unstated whole is not a measurement — and a
    source that stops being consulted should disappear from BOTH lists rather
    than silently become a permanent absence.
    """
    from set_orch.fleet.discovery import CONSULTED_SOURCES, Agent

    invented = Agent(pid=3, cwd="/x", sources=["process", "a-source-nobody-consults"])
    assert "a-source-nobody-consults" not in invented.sources_missing
    assert set(invented.sources_missing) <= set(CONSULTED_SOURCES)


# --------------------------------------------------------------------------- #
# proof — group 9
# --------------------------------------------------------------------------- #

def test_an_agent_with_neither_a_record_nor_a_log_is_listed_anyway(tmp_path):
    """Task 9.12, and it names the weaker shape it refuses: driving this from an
    `Agent` with its fields blanked tests the dataclass, not the discovery. The
    difference matters because the bug this guards is *upstream* — a lookup that
    raises, a dict access that assumes a key, a filter that drops what it cannot
    resolve — and none of that runs when the object is built by hand.

    So this drives a `/proc` that genuinely holds an agent, with a record
    directory that genuinely holds nothing about it.
    """
    from set_orch.fleet.discovery import discover_agents

    proc = tmp_path / "proc"
    (proc / "4242").mkdir(parents=True)
    (proc / "4242" / "comm").write_text("claude\n")
    (proc / "4242" / "cmdline").write_bytes(b"claude\x00")
    (proc / "4242" / "cwd").symlink_to(tmp_path)
    empty_records = tmp_path / "no-records"
    empty_records.mkdir()

    agents = discover_agents(proc_root=str(proc), record_dir=empty_records,
                             log_root=tmp_path / "no-logs")
    assert [a.pid for a in agents] == [4242]
    only = agents[0]
    assert only.session_id is None and only.session_log is None
    assert only.binding_confirmed is False
    assert only.sources == ["process"]
    assert only.sources_missing == ["session-record", "registry"]


def test_a_binding_is_never_guessed_and_an_unlabelled_guess_would_fail_here(tmp_path):
    """Task 9.1's rule, driven rather than described: a labelled guess is not a
    failure, an unlabelled one is. There is currently no guessing path at all, so
    the assertion is that every binding present is CONFIRMED — which is a
    stronger statement than "guesses are labelled", and it fails the moment a
    heuristic is added without a label.
    """
    from set_orch.fleet.discovery import discover_agents

    proc = tmp_path / "proc"
    for pid in (11, 22):
        d = proc / str(pid)
        d.mkdir(parents=True)
        (d / "comm").write_text("claude\n")
        (d / "cmdline").write_bytes(b"claude\x00")
        (d / "cwd").symlink_to(tmp_path)

    records = tmp_path / "records"
    records.mkdir()
    logs = tmp_path / "logs"
    (logs / "proj").mkdir(parents=True)
    (logs / "proj" / "sess-11.jsonl").write_text("{}\n")
    (records / "11.json").write_text(json.dumps({"pid": 11, "sessionId": "sess-11"}))

    agents = {a.pid: a for a in discover_agents(proc_root=str(proc), record_dir=records, log_root=logs)}
    assert agents[11].binding_confirmed is True and agents[11].session_id == "sess-11"
    # 22 has a log lying next to 11's in the same tree and a plausible cwd. Preferring
    # no binding to an arbitrary one is the whole rule.
    assert agents[22].session_id is None and agents[22].binding_confirmed is False


def test_two_worktrees_of_one_repository_are_one_project(tmp_path, monkeypatch):
    """Task 9.3's first half — the case that produced the phantom project. Two
    checkouts of one repository are one thing the user thinks about, and
    reporting them as two puts the same work on the screen twice under different
    names.
    """
    from set_orch.fleet import discovery as disc

    common = str(tmp_path / "repo" / ".git")
    monkeypatch.setattr(disc, "_git_common_dir", lambda cwd: common)
    a_root, a_name = disc.resolve_project(str(tmp_path / "repo"))
    b_root, b_name = disc.resolve_project(str(tmp_path / "worktrees" / "feature-x"))
    assert (a_root, a_name) == (b_root, b_name)
