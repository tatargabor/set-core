"""The macOS backend, tested on any platform.

The record, the reconciliation and the survivability refusal are ordinary Python
and are driven directly here, so a Linux CI covers them. What cannot be tested
without Darwin — that a session leader actually survives `launchctl kickstart -k`
— is a measurement, is recorded in the change's design note, and is deliberately
NOT asserted here: a unit test that mocked it would report the property proven
while proving nothing.
"""
from __future__ import annotations

import os

import pytest

from set_orch.fleet.scopes import _darwin as darwin
from set_orch.fleet.scopes._types import SCOPE_PREFIX, Scope, ScopeError, unit_name


@pytest.fixture(autouse=True)
def record_in(monkeypatch, sock_dir):
    """Point the backend's record at a temp directory, not the real runtime one.

    `_is_finished` is stubbed to False as the default so that a fabricated pid
    reads as a running agent. Without it the real `ps` runs against a pid that
    does not exist, prints nothing, and — correctly — reports finished, so every
    test about a LIVE agent would fail for a reason that has nothing to do with
    what it is testing. Tests about ending override it.
    """
    monkeypatch.setattr(darwin, "_record_path", lambda: str(sock_dir / "agents.json"))
    monkeypatch.setattr(darwin, "_is_finished", lambda pid: False)


# --- the survivability refusal --------------------------------------------- #

def test_a_process_that_does_not_lead_its_own_session_is_refused(monkeypatch):
    """The check that carries the whole survival promise. Refuse, never warn: the
    surface presents a started agent as one that outlives a restart, so a start
    that quietly lacks the property makes the screen state something false."""
    monkeypatch.setattr(darwin.os, "getsid", lambda pid: 1)      # launchd's session
    monkeypatch.setattr(darwin.os, "getpgid", lambda pid: pid)

    with pytest.raises(ScopeError) as excinfo:
        darwin.assert_survivable("set-agent-x.scope", 4242)

    message = str(excinfo.value)
    assert "4242" in message and "session 1" in message
    assert "would die with it" in message


def test_a_session_leader_in_someone_elses_process_group_is_refused(monkeypatch):
    """Leading a session is not enough on its own — a signal to a group it joined
    would still reach it, and the group is the thing `stop()` signals."""
    monkeypatch.setattr(darwin.os, "getsid", lambda pid: pid)
    monkeypatch.setattr(darwin.os, "getpgid", lambda pid: 99)

    with pytest.raises(ScopeError, match="process group"):
        darwin.assert_survivable("set-agent-x.scope", 4242)


def test_a_session_leader_of_its_own_group_is_accepted(monkeypatch):
    monkeypatch.setattr(darwin.os, "getsid", lambda pid: pid)
    monkeypatch.setattr(darwin.os, "getpgid", lambda pid: pid)

    assert darwin.assert_survivable("set-agent-x.scope", 4242) == ""


def test_a_pid_that_cannot_be_read_is_refused_rather_than_assumed_fine(monkeypatch):
    """The direction matters. An unreadable session is not evidence of safety, and
    defaulting to "fine" would let exactly the unverifiable case through."""
    def boom(pid):
        raise ProcessLookupError(pid)
    monkeypatch.setattr(darwin.os, "getsid", boom)

    with pytest.raises(ScopeError, match="cannot read the session"):
        darwin.assert_survivable("set-agent-x.scope", 4242)


def test_no_pid_at_all_is_refused(monkeypatch):
    with pytest.raises(ScopeError, match="no pid to verify"):
        darwin.assert_survivable("set-agent-x.scope", None)


# --- the record ------------------------------------------------------------ #

def _adopt(monkeypatch, unit, pid, started="Thu Aug 27 16:29:44 2026", cwd="/tmp/x"):
    monkeypatch.setattr(darwin.os, "getsid", lambda p: p)
    monkeypatch.setattr(darwin.os, "getpgid", lambda p: p)
    monkeypatch.setattr(darwin, "_started_at", lambda p: started)
    return darwin.adopt(unit, pid, cwd)


def test_an_adopted_agent_is_found_by_its_name(monkeypatch):
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)

    scope = darwin.get(unit)
    assert scope is not None
    assert scope.pid == 4242
    assert scope.active is True
    assert scope.label == "demo"


def test_enumeration_survives_an_owner_restart(monkeypatch):
    """The record is the whole point: systemd enumerates its units for free and
    macOS has nothing equivalent, so a restarted owner would otherwise know
    nothing about the agents it is still holding terminals for."""
    _adopt(monkeypatch, unit_name("a"), 1)
    _adopt(monkeypatch, unit_name("b"), 2)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)

    # Nothing carried over in memory — a fresh read, as a new process would do.
    listed = {s.label for s in darwin.list_scopes()}
    assert listed == {"a", "b"}


def test_a_stale_entry_is_reported_gone_not_alive(monkeypatch):
    unit = unit_name("ended")
    _adopt(monkeypatch, unit, 4242)

    def gone(pid, sig):
        raise ProcessLookupError(pid)
    monkeypatch.setattr(darwin.os, "kill", gone)

    scope = darwin.get(unit)
    assert scope is not None, "a recorded name is not the same answer as an unknown one"
    assert scope.active is False
    assert scope.pid is None
    assert darwin.is_gone(unit) is True
    assert darwin.scope_is_gone(scope) is True


def test_an_unknown_name_and_an_ended_agent_are_different_answers(monkeypatch):
    """`None` means "never recorded"; an inactive scope means "recorded, ended".
    Collapsing them would lose the distinction the caller acts on."""
    assert darwin.get(unit_name("never-existed")) is None


def test_a_recycled_pid_is_not_mistaken_for_the_agent(monkeypatch):
    """`kill(pid, 0)` alone answers "some process has this pid", which is exactly
    the question that lets a stranger inherit an agent's identity — and the
    surface would then offer to stop it."""
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242, started="Thu Aug 27 16:29:44 2026")

    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)          # a pid exists
    monkeypatch.setattr(darwin, "_started_at", lambda p: "Thu Aug 27 18:99:99 2026")

    scope = darwin.get(unit)
    assert scope.active is False, "the pid was reused and the agent reported alive"
    assert darwin.scope_of(4242) is None


def test_the_same_pid_with_the_same_start_time_is_the_agent(monkeypatch):
    """The negative test above needs this one beside it: a guard that says 'gone'
    to everything would pass it while breaking the fleet."""
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242, started="Thu Aug 27 16:29:44 2026")
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)

    assert darwin.get(unit).active is True
    assert darwin.scope_of(4242) == unit


def test_forget_drops_the_name(monkeypatch):
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242)
    darwin.forget(unit)

    assert darwin.get(unit) is None


def test_a_corrupt_record_does_not_read_as_an_empty_one_silently(monkeypatch, sock_dir, caplog):
    """It still returns empty — the fleet must not fall over — but it says so.
    An empty record invites starting an agent under a name that may be taken."""
    (sock_dir / "agents.json").write_text("{not json")

    with caplog.at_level("WARNING"):
        assert darwin.list_scopes() == []
    assert any("cannot read" in r.message for r in caplog.records)


# --- naming ---------------------------------------------------------------- #

def test_a_label_carries_the_frameworks_prefix(monkeypatch):
    unit = unit_name("demo")
    assert unit.startswith(SCOPE_PREFIX)
    _adopt(monkeypatch, unit, 1)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)
    assert darwin.list_scopes()[0].unit.startswith(SCOPE_PREFIX)


def test_a_bare_name_is_normalised_and_a_qualified_one_is_left_alone(monkeypatch):
    _adopt(monkeypatch, unit_name("demo"), 1)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)

    assert darwin.get("set-agent-demo") is not None      # bare, normalised
    assert darwin.get("set-agent-demo.scope") is not None
    assert darwin.get("set-web.service") is None         # not turned into .service.scope


# --- stopping -------------------------------------------------------------- #

def test_stopping_an_unknown_name_reports_gone_rather_than_failing(monkeypatch):
    assert darwin.stop(unit_name("never-existed")) is True


def test_stop_signals_the_group_not_the_pid(monkeypatch):
    """An agent's own children hold no terminal of their own. Signalling the pid
    alone leaves them running with nothing attached — the same reason the systemd
    backend stops the unit rather than its main pid."""
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242)
    sent = []
    monkeypatch.setattr(darwin.os, "getpgid", lambda p: 4242)
    monkeypatch.setattr(darwin.os, "killpg", lambda pgid, sig: sent.append((pgid, sig)))
    # Alive for the signal, gone immediately after.
    calls = {"n": 0}
    def kill(p, s):
        calls["n"] += 1
        if calls["n"] > 1:
            raise ProcessLookupError(p)
    monkeypatch.setattr(darwin.os, "kill", kill)

    assert darwin.stop(unit, grace=0.2, kill_grace=0.2) is True
    assert sent and sent[0][0] == 4242, "the process group was not signalled"
    assert darwin.get(unit) is None, "a stopped agent was left in the record"


def test_a_zombie_child_is_not_reported_alive(monkeypatch):
    """The agent is the owner's own forked child, so between its exit and its
    reaping it is a zombie — and `os.kill(pid, 0)` SUCCEEDS for one while its
    start time still matches. Measured 2026-08-27 on the first acceptance run:
    `stop()` answered `gone: false` for an agent `ps` showed was gone, and left
    it in the record, where it would have blocked its own name from being reused.
    """
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)   # the pid still resolves
    monkeypatch.setattr(darwin, "_is_finished", lambda p: True)

    assert darwin.get(unit).active is False
    assert darwin.is_gone(unit) is True


def test_a_running_process_is_not_mistaken_for_a_zombie(monkeypatch):
    """The guard's other direction: reporting every agent dead would pass the
    test above while breaking every screen."""
    unit = unit_name("demo")
    _adopt(monkeypatch, unit, 4242)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)
    monkeypatch.setattr(darwin, "_is_finished", lambda p: False)

    assert darwin.get(unit).active is True


def test_the_finished_state_is_read_from_the_process_table(monkeypatch):
    """`?Es`, not `Z`, is what an agent killed on its pty actually reports, and
    testing for the state LETTER instead of the exit FLAG cost three acceptance
    runs: `stop()` polled a dead process for its full grace and kill grace and
    then reported `survived SIGKILL`. `E` is the BSD flag for "trying to exit";
    `Z` is the documented zombie a plain forked child reports. Both mean gone.
    An empty line is `ps` finding no such pid, which is stronger still.
    """
    import subprocess as _sp
    monkeypatch.undo()
    monkeypatch.setattr(darwin, "_record_path", lambda: "/tmp/unused-agents.json")
    for state, expected in (
        ("Z", True), ("Z+", True), ("?Es", True), ("?E", True),
        ("S", False), ("R", False), ("Ss+", False), ("I", False), ("", True),
    ):
        monkeypatch.setattr(
            darwin.subprocess, "run",
            lambda *a, _s=state, **k: _sp.CompletedProcess(a[0], 0, _s + "\n", ""),
        )
        assert darwin._is_finished(4242) is expected, state


def test_the_record_does_not_grow_without_bound(monkeypatch):
    """Nothing else prunes it. Without this the file accumulates every agent the
    machine has ever started, and a `list_scopes()` cost grows with history
    rather than with the fleet.

    Pruned at a WRITE, never on a read: `get()` answers "never recorded" and
    "recorded and ended" differently, and dropping an entry mid-read would flip
    a name from the second to the first under a caller acting on it.
    """
    ended, live = unit_name("ended"), unit_name("live")
    _adopt(monkeypatch, ended, 1)

    monkeypatch.setattr(darwin, "_is_finished", lambda pid: pid == 1)
    monkeypatch.setattr(darwin.os, "kill", lambda p, s: None)
    _adopt(monkeypatch, live, 2)
    monkeypatch.setattr(darwin, "_is_finished", lambda pid: pid == 1)

    names = set(darwin._read_record())
    assert live in names
    assert ended not in names, "an ended agent was kept in the record for ever"


def test_pruning_never_touches_a_live_agent(monkeypatch):
    """The other direction, and the one that would lose work: a prune that
    dropped live entries would make the fleet forget agents it is still holding
    terminals for."""
    a, b = unit_name("a"), unit_name("b")
    _adopt(monkeypatch, a, 1)
    _adopt(monkeypatch, b, 2)

    assert set(darwin._read_record()) == {a, b}
