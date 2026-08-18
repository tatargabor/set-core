"""The agent owner and its scopes — tasks 5.8, 5.9, 5.11.

These tests do not need systemd: the parts that talk to it are replaced, and
what is asserted is the *decision logic*, which is where the hazards are. The
systemd behaviour itself was verified live on 2026-08-18 and is recorded in the
module docstrings and in design §6.2 — including the two results that changed
the design (a pty-attached agent dies with its pty holder; an interactive shell
ignores SIGTERM, so `stop` must escalate).

The load-bearing test here is `test_recover_refuses_to_resume_when_the_scope_will
_not_die`. Everything else in this file guards a mistake that would be noticed;
that one guards a mistake that is silent — two live sessions appending to one
transcript, neither aware of the other.
"""

from __future__ import annotations

import pytest

from set_orch.fleet import owner as owner_mod
from set_orch.fleet import scopes as scopes_mod
from set_orch.fleet.owner import AgentOwner, OwnerError, recover, FOREIGN, STARTED_HERE
from set_orch.fleet.scopes import Scope, ScopeError


# --------------------------------------------------------------------------- #
# scopes
# --------------------------------------------------------------------------- #

def test_a_scope_inside_the_service_cgroup_is_refused_not_warned(monkeypatch):
    """The whole point of the module. A scope that came out as a child of the
    service would die with it, while the surface went on promising survival —
    so this refuses rather than logs.
    """
    svc = "/user.slice/user@1000.service/app.slice/set-web.service"
    monkeypatch.setattr(scopes_mod, "_show", lambda unit, prop: svc + "/agent" if prop == "ControlGroup" else "active")
    monkeypatch.setattr(scopes_mod, "service_cgroup", lambda service="set-web.service": svc)
    with pytest.raises(ScopeError) as excinfo:
        scopes_mod.assert_sibling("set-agent-x.scope")
    assert "INSIDE" in str(excinfo.value)


def test_a_sibling_scope_is_accepted(monkeypatch):
    svc = "/user.slice/user@1000.service/app.slice/set-web.service"
    sib = "/user.slice/user@1000.service/app.slice/set-agent-x.scope"
    monkeypatch.setattr(scopes_mod, "_show", lambda unit, prop: sib if prop == "ControlGroup" else "active")
    monkeypatch.setattr(scopes_mod, "service_cgroup", lambda service="set-web.service": svc)
    assert scopes_mod.assert_sibling("set-agent-x.scope") == sib


def test_a_prefix_of_the_service_path_is_not_a_parent(monkeypatch):
    """`/…/set-web.service` and `/…/set-web.service-extra` share a prefix and are
    unrelated cgroups. A `startswith` without the separator would refuse a
    perfectly good scope — and the refusal would look like the guard working.
    """
    svc = "/user.slice/app.slice/set-web.service"
    monkeypatch.setattr(scopes_mod, "_show", lambda unit, prop: svc + "-extra/x.scope" if prop == "ControlGroup" else "active")
    monkeypatch.setattr(scopes_mod, "service_cgroup", lambda service="set-web.service": svc)
    assert scopes_mod.assert_sibling("set-agent-x.scope")


def test_stopping_a_unit_that_is_not_ours_is_refused(monkeypatch):
    monkeypatch.setattr(scopes_mod, "_systemctl", lambda *a, **k: pytest.fail("must not reach systemctl"))
    for name in ("set-web.service", "user@1000.service", "something.scope"):
        with pytest.raises(ScopeError):
            scopes_mod.stop(name)


def test_a_label_that_needed_sanitising_cannot_collide_with_another():
    """Two different labels must not become one unit name. A scope IS an identity
    here, so a collision would stop the wrong agent.
    """
    a = scopes_mod.unit_name("feat/one")
    b = scopes_mod.unit_name("feat:one")
    assert a != b
    assert scopes_mod.unit_name("plain") == "set-agent-plain.scope"


def test_stop_escalates_to_sigkill_when_sigterm_is_ignored(monkeypatch):
    """Measured 2026-08-18: an interactive shell in a scope ignored SIGTERM and
    kept `systemctl stop` blocked past 20 s. A stop that hangs forever is not a
    gentler stop — it is a stop that did not happen.
    """
    calls = []

    def fake_systemctl(*args, **kwargs):
        calls.append(args)
        import subprocess
        return subprocess.CompletedProcess(list(args), 0, "", "")

    state = {"active": True}

    def fake_get(unit):
        return Scope(unit=unit, pid=1, cgroup="/x", active=state["active"])

    def fake_await(unit, seconds, interval=0.2):
        # SIGTERM window: still alive. After the kill call, report it gone.
        if any("kill" in a for a in calls[-1]):
            state["active"] = False
        return not state["active"]

    monkeypatch.setattr(scopes_mod, "_systemctl", fake_systemctl)
    monkeypatch.setattr(scopes_mod, "get", fake_get)
    monkeypatch.setattr(scopes_mod, "_await_gone", fake_await)

    assert scopes_mod.stop("set-agent-x.scope") is True
    assert any("stop" in a for a in calls), calls
    assert any("kill" in a for a in calls), "SIGTERM was ignored and nothing escalated"


# --------------------------------------------------------------------------- #
# owner
# --------------------------------------------------------------------------- #

def _owner_with(label: str | None = None) -> AgentOwner:
    o = AgentOwner()
    if label:
        o._agents[label] = owner_mod.OwnedAgent(
            label=label, unit=scopes_mod.unit_name(label), pid=1,
            cwd="/tmp", master_fd=-1,
        )
    return o


def test_the_framework_never_writes_into_a_session_it_did_not_start():
    """Task 5.2, and the check is structural rather than a rule: this owner can
    only write to a master it is holding, so the refusal cannot drift out of
    agreement with reality.
    """
    o = _owner_with()
    with pytest.raises(OwnerError) as excinfo:
        o.write("someone-elses-session", b"rm -rf /\n")
    assert "did not start" in str(excinfo.value)


def test_population_is_about_the_handle_not_about_history():
    o = _owner_with("mine")
    assert o.population_of("mine") == STARTED_HERE
    # Started by the framework, but by a PREVIOUS owner: this one holds no handle,
    # so it cannot be typed into, and that is the property the surface needs.
    assert o.population_of("set-agent-from-a-dead-owner.scope") == FOREIGN


def test_orphans_are_live_framework_scopes_this_owner_does_not_hold(monkeypatch):
    live = [
        Scope(unit="set-agent-mine.scope", pid=1, pids=[1], cgroup="/x", active=True, state="active"),
        Scope(unit="set-agent-stray.scope", pid=2, pids=[2], cgroup="/x", active=True, state="active"),
        Scope(unit="set-agent-dead.scope", pid=None, cgroup="/x", active=False, state="inactive"),
    ]
    monkeypatch.setattr(scopes_mod, "list_scopes", lambda: live)
    o = _owner_with("mine")
    assert [s.unit for s in o.orphans()] == ["set-agent-stray.scope"]


# --------------------------------------------------------------------------- #
# recovery — the order is the whole of it
# --------------------------------------------------------------------------- #

def test_recover_stops_the_old_scope_before_it_resumes(monkeypatch):
    order = []
    monkeypatch.setattr(scopes_mod, "get", lambda u: Scope(unit=u, pid=None, cgroup="/x", active=False, state="inactive")
                        if order else Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))

    def fake_stop(unit, **kw):
        order.append("stop")
        return True

    monkeypatch.setattr(scopes_mod, "stop", fake_stop)
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: order.append("resume") or "started")

    recover(o, unit="set-agent-x.scope", session_id="s1", cwd="/tmp")
    assert order == ["stop", "resume"]


def test_recover_refuses_to_resume_when_the_scope_will_not_die(monkeypatch):
    """The silent hazard, and the only reason this function exists as code rather
    than as an instruction. Resuming against a live session forks its
    conversation: two sessions append to one transcript, neither aware of the
    other, and nothing reports it (design §6.1). So a stop that did not take
    aborts the recovery — it does not proceed hopefully.
    """
    monkeypatch.setattr(scopes_mod, "get",
                        lambda u: Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))
    monkeypatch.setattr(scopes_mod, "stop", lambda unit, **kw: False)
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: pytest.fail("resumed against a live session"))

    with pytest.raises(OwnerError) as excinfo:
        recover(o, unit="set-agent-x.scope", session_id="s1", cwd="/tmp")
    assert "forks" in str(excinfo.value)


def test_recover_rechecks_the_state_rather_than_trusting_the_stop_call(monkeypatch):
    """A stop that returns True and leaves the unit running is the same hazard
    wearing a success. The state now is the fact; the call's opinion of it a
    moment ago is not.
    """
    monkeypatch.setattr(scopes_mod, "get",
                        lambda u: Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))
    monkeypatch.setattr(scopes_mod, "stop", lambda unit, **kw: True)   # lies
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: pytest.fail("resumed against a live session"))

    with pytest.raises(OwnerError) as excinfo:
        recover(o, unit="set-agent-x.scope", session_id="s1", cwd="/tmp")
    assert "is not gone" in str(excinfo.value)


def test_a_resumed_agent_says_it_was_resumed(monkeypatch):
    """The surface must be able to say which of the two acts it performed —
    replacement is not reattachment, and reporting it as one would promise a
    continuity the mechanism does not have.
    """
    monkeypatch.setattr(scopes_mod, "get", lambda u: None)
    captured = {}
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: captured.update(k) or "ok")
    recover(o, unit="set-agent-x.scope", session_id="sess-42", cwd="/tmp")
    assert captured["resumed_session"] == "sess-42"


# --------------------------------------------------------------------------- #
# "gone" is about the PROCESSES — measured 2026-08-18 on a live agent
# --------------------------------------------------------------------------- #

def test_a_deactivating_scope_holding_a_live_pid_is_not_gone():
    """The defect this file did not catch, and it failed in the reassuring
    direction. Measured on a real interactive agent: `stop()` returned
    `gone=True` in **0.0 seconds** and logged "stopped on SIGTERM" while
    `systemctl show` said `deactivating` and the agent's pid was still alive.

    The cause was a lossy conversion, not a missing wait: `Scope.active` is the
    string comparison `ActiveState == "active"`, so every intermediate state read
    as "not active" — which the stop path had been treating as "gone".
    """
    shutting_down = Scope(unit="set-agent-x.scope", pid=99, pids=[99],
                          cgroup="/x", active=False, state="deactivating")
    assert shutting_down.active is False          # it really is not active …
    assert scopes_mod.scope_is_gone(shutting_down) is False   # … and it is NOT gone


def test_a_bare_not_active_check_would_not_have_caught_it():
    """Holds the pattern that was WRONG, so a later simplification back to
    `not scope.active` fails here instead of looking identical and reporting a
    running agent as stopped.
    """
    for state in ("activating", "deactivating", "reloading"):
        scope = Scope(unit="set-agent-x.scope", pid=7, pids=[7],
                      cgroup="/x", active=False, state=state)
        assert not scope.active, "the old check would have called this gone"
        assert not scopes_mod.scope_is_gone(scope), f"{state} with a live pid is not gone"


def test_an_inactive_scope_with_no_processes_is_gone():
    """The other direction matters as much: if nothing ever counts as gone, a
    stop can never finish and recovery can never start.
    """
    finished = Scope(unit="set-agent-x.scope", pid=None, pids=[],
                     cgroup="", active=False, state="inactive")
    assert scopes_mod.scope_is_gone(finished) is True
    assert scopes_mod.scope_is_gone(None) is True


def test_recover_refuses_while_the_old_scope_is_still_shutting_down(monkeypatch):
    """The §6.1 fork guard, in the exact shape that was open.

    `recover()` re-reads the state rather than trusting `stop()`'s return — but a
    re-read is only a guard if it asks a DIFFERENT question than the one that can
    be wrong. It asked `still.active`, which is precisely what the stop path had
    already mis-answered, so a scope that was `deactivating` with a live agent in
    it passed both checks and the resume went ahead against a running session.
    """
    monkeypatch.setattr(
        scopes_mod, "get",
        lambda u: Scope(unit=u, pid=5, pids=[5], cgroup="/x", active=False, state="deactivating"),
    )
    monkeypatch.setattr(scopes_mod, "stop", lambda unit, **kw: True)   # claims success
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: pytest.fail("resumed against a live session"))

    with pytest.raises(OwnerError) as excinfo:
        recover(o, unit="set-agent-x.scope", session_id="s1", cwd="/tmp")
    assert "is not gone" in str(excinfo.value)
    assert "[5]" in str(excinfo.value), "the refusal must name the pids that are still there"


def test_a_scope_that_is_shutting_down_is_still_listed_as_an_orphan(monkeypatch):
    """And it is the orphan most worth showing — the one that will not die on
    its own. Excluding it would hide exactly the case a human has to act on.
    """
    live = [Scope(unit="set-agent-stray.scope", pid=2, pids=[2],
                  cgroup="/x", active=False, state="deactivating")]
    monkeypatch.setattr(scopes_mod, "list_scopes", lambda: live)
    assert [s.unit for s in AgentOwner().orphans()] == ["set-agent-stray.scope"]
