"""Discovery on a platform without `/proc` — driven on either platform.

`tests/unit/test_fleet_discovery.py` drives the same functions against a fake
`/proc` tree and is deliberately untouched by the `macos-fleet-discovery` change;
that it still passes is the evidence the Linux path did not move. This file is
the other half: the same functions, with the macOS backend selected, from
recorded `ps` and `lsof` output.

The measurement these tests stand in for, from a machine with two live agent
sessions on 2026-08-27:

    before   discover_agents()          -> []
             is_agent_process(37343)    -> False
    after    discover_agents()          -> 2 agents, correct cwd/project/branch
             is_agent_process(37343)    -> True
"""
from __future__ import annotations

import subprocess

import pytest

from set_orch.fleet import discovery, procsource
from set_orch.fleet.procsource import _darwin


PS_IDENTITY = (
    "    1     0 /sbin/launchd\n"
    "37343 37323 claude\n"
    "37323 37322 -zsh\n"
    "40000     1 claude\n"
)

PS_ARGS = (
    "37343 claude --dangerously-skip-permissions\n"
    "37323 -zsh\n"
    "40000 claude -p summarise this\n"
)

LSOF = (
    "p37343\nfcwd\nn/Users/x/code/project-a\n"
    "p40000\nfcwd\nn/Users/x/code/project-b\n"
)


class FakeRun:
    """A `ps`/`lsof` stand-in that answers the per-pid queries from the same
    recorded table as the whole-table ones.

    Answering them from one source is the point: a fixture that let the two
    disagree would let a test pass while the real backend read a pid out of a
    table it was not in.
    """

    def __init__(self, answers):
        self.answers = answers
        self.calls = []
        self.rows = {}
        for line in PS_IDENTITY.splitlines():
            pid, ppid, comm = line.split(None, 2)
            self.rows[pid] = (ppid, comm)

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if argv[0].endswith("ps") and "-p" in argv and "-A" not in argv:
            pid = argv[argv.index("-p") + 1]
            ppid_comm = self.rows.get(pid)
            if ppid_comm is None:
                return subprocess.CompletedProcess(argv, 1, "", "")
            ppid, comm = ppid_comm
            if joined.endswith("pid=,comm="):
                return subprocess.CompletedProcess(argv, 0, f"{pid} {comm}\n", "")
            if joined.endswith("pid=,ppid="):
                return subprocess.CompletedProcess(argv, 0, f"{pid} {ppid}\n", "")
        for key, (rc, out, err) in self.answers.items():
            if key in joined:
                return subprocess.CompletedProcess(argv, rc, out, err)
        return subprocess.CompletedProcess(argv, 1, "", "")


@pytest.fixture
def on_macos(monkeypatch):
    """Select the Darwin backend and feed it recorded output.

    Git resolution is stubbed out — it shells out per agent and answers about the
    machine the test runs on, which is a different question from the one here.
    """
    run = FakeRun({
        "pid=,ppid=,comm=": (0, PS_IDENTITY, ""),
        "pid=,args=": (0, PS_ARGS, ""),
        "lsof": (0, LSOF, ""),
    })
    monkeypatch.setattr(procsource, "BACKEND", "darwin")
    monkeypatch.setattr(_darwin.subprocess, "run", run)
    monkeypatch.setattr(discovery, "resolve_project", lambda cwd: (cwd, cwd.rsplit("/", 1)[-1]))
    monkeypatch.setattr(discovery, "_git_branch", lambda cwd: "main")
    monkeypatch.setattr(discovery, "_load_session_records", lambda d: {})
    return run


# --- the defect this change repaired ---------------------------------------- #

def test_live_agents_are_listed_with_their_working_directories(on_macos):
    agents = discovery.discover_agents()
    assert [a.pid for a in agents] == [37343]
    assert agents[0].cwd == "/Users/x/code/project-a"
    assert agents[0].project_name == "project-a"
    assert agents[0].kind == "interactive"


def test_a_live_pid_verifies_as_an_agent(on_macos):
    assert discovery.is_agent_process(37343) is True
    assert discovery.is_agent_process(37323) is False       # the shell above it


def test_a_one_shot_subprocess_is_still_excluded_by_default(on_macos):
    """`-p` arrives here from a space-split command line rather than from a
    NUL-separated `cmdline`, which is the one place the platform's loss of exact
    argument separation could have changed an answer. It does not: the test is
    membership of a flag, and a flag has no spaces in it."""
    assert 40000 not in [a.pid for a in discovery.discover_agents()]
    assert 40000 in [a.pid for a in discovery.discover_agents(include_oneshot=True)]


def test_a_pid_that_is_not_an_agent_is_still_rejected(on_macos):
    assert discovery.discover_agent(37323) is None


def test_an_agent_with_no_readable_cwd_is_omitted_not_invented(monkeypatch, on_macos):
    """A process that exits between the `ps` and the `lsof` has no cwd. It drops
    out of the listing, which is an omission; what must never happen is a tile
    with a guessed directory under it."""
    monkeypatch.setattr(_darwin, "cwds", lambda pids: {p: None for p in pids})
    assert discovery.discover_agents() == []


# --- the reads are batched -------------------------------------------------- #

def test_one_pass_reads_the_table_and_the_directories_in_batches(on_macos):
    """Three subprocesses per pass rather than two per agent. On `/proc` this is
    the same file reads in a different order; here each read is a fork."""
    discovery.discover_agents()
    lsof_calls = [c for c in on_macos.calls if c[0].endswith("lsof")]
    assert len(lsof_calls) == 1
    assert len([c for c in on_macos.calls if "-A" in c]) == 2   # identity + args


# --- ancestry, where the right answer and the blind one are the same value --- #

def test_the_ancestry_walk_actually_runs_before_reporting_no_seat(on_macos, monkeypatch):
    """`parent_seat` returns None on Linux for a documented, measured reason — 0
    of 23 live agents had an agent ancestor, and a framework-started agent's
    parent is the owner process. So `assert parent_seat(pid) is None` passes
    against an implementation that never looked, which is exactly what the macOS
    code was doing. The walk is asserted, not just its result.

    The chain in the fixture is the real one measured on 2026-08-27:
    claude(37343) -> zsh(37323) -> ... -> launchd(1), with no agent above.
    """
    climbed = []
    real_ppid = _darwin.ppid
    monkeypatch.setattr(_darwin, "ppid", lambda pid: climbed.append(pid) or real_ppid(pid))

    assert discovery.parent_seat(37343) is None
    assert climbed, "parent_seat reported no seat without reading a single parent pid"
    assert 37343 in climbed


def test_the_walk_reports_the_seat_of_an_agent_ancestor(monkeypatch, on_macos):
    """Two links away, not one: an agent that runs the binary from its own shell
    has a shell in between, so the walk climbs through non-agents."""
    monkeypatch.setattr(discovery, "_load_session_records",
                        lambda d: {40000: {"name": "seat-b", "sessionId": "sid-b"}})
    monkeypatch.setattr(_darwin, "ppid", {9001: 37323, 37323: 40000}.get)
    monkeypatch.setattr(_darwin, "comm", lambda pid: "claude" if pid == 40000 else "zsh")

    seat = discovery.parent_seat(9001)
    assert seat["seat"] == "seat-b"
    assert seat["session_id"] == "sid-b"
    assert seat["source"] == "ancestry"


# --- the fail direction that must survive the platform ---------------------- #

def test_an_unreadable_table_is_undeterminable_liveness_not_an_empty_set(monkeypatch, on_macos):
    monkeypatch.setattr(_darwin, "live_pids", lambda name: None)
    assert discovery.live_session_ids() is None


def test_an_unreadable_table_is_an_empty_listing(monkeypatch, on_macos):
    """The opposite direction, for the opposite caller: a listing that cannot see
    shows nothing, and that is honest. Both behaviours in one file on purpose —
    they look like an inconsistency until you know which caller each serves."""
    monkeypatch.setattr(_darwin, "live_pids", lambda name: None)
    assert discovery.discover_agents() == []
