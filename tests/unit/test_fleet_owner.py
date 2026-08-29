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
# The systemd backend, patched directly. `scopes` delegates to it at access
# time, so calling through `scopes_mod` still reaches whatever is installed
# here — but a fake must be installed on the module whose GLOBALS the code
# under test reads. Patching the package would shadow the name for a caller
# reaching through it and leave `assert_sibling`'s own `_show` untouched, which
# is the half that decides the answer.
from set_orch.fleet.scopes import _systemd as scopes_backend


@pytest.fixture(autouse=True)
def _pin_the_systemd_backend(monkeypatch):
    """Every test in this file drives the SYSTEMD backend, so it says so.

    `scopes` picks a backend from `sys.platform` at import, and its delegation
    resolves through the module-global `_backend` on every access — so pinning it
    here redirects the whole package for the duration of one test, without the
    file having to know which platform it is running on.

    Without this the file silently tested whichever backend the developer's
    machine happened to select: green on Linux, and on macOS thirteen failures
    that look like product defects and are not. The macOS backend has its own
    file; a shared one would test neither properly.
    """
    from set_orch.fleet import scopes as _scopes
    monkeypatch.setattr(_scopes, "_backend", scopes_backend)
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
    monkeypatch.setattr(scopes_backend, "_show", lambda unit, prop: svc + "/agent" if prop == "ControlGroup" else "active")
    monkeypatch.setattr(scopes_backend, "service_cgroup", lambda service="set-web.service": svc)
    with pytest.raises(ScopeError) as excinfo:
        scopes_mod.assert_sibling("set-agent-x.scope")
    assert "INSIDE" in str(excinfo.value)


def test_a_sibling_scope_is_accepted(monkeypatch):
    svc = "/user.slice/user@1000.service/app.slice/set-web.service"
    sib = "/user.slice/user@1000.service/app.slice/set-agent-x.scope"
    monkeypatch.setattr(scopes_backend, "_show", lambda unit, prop: sib if prop == "ControlGroup" else "active")
    monkeypatch.setattr(scopes_backend, "service_cgroup", lambda service="set-web.service": svc)
    assert scopes_mod.assert_sibling("set-agent-x.scope") == sib


def test_a_prefix_of_the_service_path_is_not_a_parent(monkeypatch):
    """`/…/set-web.service` and `/…/set-web.service-extra` share a prefix and are
    unrelated cgroups. A `startswith` without the separator would refuse a
    perfectly good scope — and the refusal would look like the guard working.
    """
    svc = "/user.slice/app.slice/set-web.service"
    monkeypatch.setattr(scopes_backend, "_show", lambda unit, prop: svc + "-extra/x.scope" if prop == "ControlGroup" else "active")
    monkeypatch.setattr(scopes_backend, "service_cgroup", lambda service="set-web.service": svc)
    assert scopes_mod.assert_sibling("set-agent-x.scope")


def test_stopping_a_unit_that_is_not_ours_is_refused(monkeypatch):
    monkeypatch.setattr(scopes_backend, "_systemctl", lambda *a, **k: pytest.fail("must not reach systemctl"))
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

    monkeypatch.setattr(scopes_backend, "_systemctl", fake_systemctl)
    monkeypatch.setattr(scopes_backend, "get", fake_get)
    monkeypatch.setattr(scopes_backend, "_await_gone", fake_await)

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
    monkeypatch.setattr(scopes_backend, "list_scopes", lambda: live)
    o = _owner_with("mine")
    assert [s.unit for s in o.orphans()] == ["set-agent-stray.scope"]


# --------------------------------------------------------------------------- #
# recovery — the order is the whole of it
# --------------------------------------------------------------------------- #

def test_recover_stops_the_old_scope_before_it_resumes(monkeypatch):
    order = []
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    monkeypatch.setattr(scopes_backend, "get", lambda u: Scope(unit=u, pid=None, cgroup="/x", active=False, state="inactive")
                        if order else Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))

    def fake_stop(unit, **kw):
        order.append("stop")
        return True

    monkeypatch.setattr(scopes_backend, "stop", fake_stop)
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
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    monkeypatch.setattr(scopes_backend, "get",
                        lambda u: Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))
    monkeypatch.setattr(scopes_backend, "stop", lambda unit, **kw: False)
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
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    monkeypatch.setattr(scopes_backend, "get",
                        lambda u: Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))
    monkeypatch.setattr(scopes_backend, "stop", lambda unit, **kw: True)   # lies
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
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
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
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    monkeypatch.setattr(
        scopes_backend, "get",
        lambda u: Scope(unit=u, pid=5, pids=[5], cgroup="/x", active=False, state="deactivating"),
    )
    monkeypatch.setattr(scopes_backend, "stop", lambda unit, **kw: True)   # claims success
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
    monkeypatch.setattr(scopes_backend, "list_scopes", lambda: live)
    assert [s.unit for s in AgentOwner().orphans()] == ["set-agent-stray.scope"]


# --------------------------------------------------------------------------- #
# stopping says what it FOUND — measured 2026-08-18 through the HTTP route
# --------------------------------------------------------------------------- #

def test_stopping_a_name_that_is_not_running_anywhere_reports_no_find(monkeypatch):
    """It used to report success. `POST /api/fleet/agents/<never-existed>/stop`
    answered `{"gone": true}` with a 200, because `scopes.stop` on an unknown
    unit finds nothing running and "nothing is running" is technically true.

    It is also a false value: the screen would confirm that an agent had been
    stopped when there had never been one. The three outcomes are different acts
    and the caller is told which one happened.
    """
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(scopes_backend, "stop",
                        lambda *a, **kw: pytest.fail("must not try to stop what is not there"))
    result = AgentOwner().stop("never-existed")
    assert result["found"] is False
    assert result["population"] is None


def test_stopping_an_orphan_is_allowed_and_named_as_one(monkeypatch):
    """A framework scope whose terminal died with a previous owner is still
    stoppable — it is the first half of `recover()`. What must not happen is
    reporting it as though this owner had been holding it.
    """
    monkeypatch.setattr(
        scopes_backend, "get",
        lambda u: Scope(unit=u, pid=4, pids=[4], cgroup="/x", active=True, state="active"),
    )
    monkeypatch.setattr(scopes_backend, "stop", lambda *a, **kw: True)
    result = AgentOwner().stop("someone-elses")
    assert result["found"] is True
    assert result["population"] == FOREIGN
    assert result["gone"] is True


def test_stopping_an_agent_this_owner_holds_says_so(monkeypatch):
    monkeypatch.setattr(scopes_backend, "stop", lambda *a, **kw: True)
    o = _owner_with("mine")
    result = o.stop("mine")
    assert result["found"] is True
    assert result["population"] == STARTED_HERE
    assert o.owned() == []


# --------------------------------------------------------------------------- #
# never resume a session something is already running — task 5.7
# --------------------------------------------------------------------------- #

def test_a_session_a_live_process_is_bound_to_is_never_resumed(monkeypatch):
    """The check is on the SESSION, not on the unit, and that is the whole point.

    Stopping the scope covers the agents this framework started. It says nothing
    about the rest, and the rest is most of them: a session started by hand has
    no scope, so every unit-based check clears it for resume — and a resume
    against a live session forks its conversation into a branch the running
    original never sees, with nothing reporting it (design §6.1).
    """
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: {"live-one"})
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: pytest.fail("resumed against a live session"))

    with pytest.raises(OwnerError) as excinfo:
        recover(o, unit="set-agent-x.scope", session_id="live-one", cwd="/tmp")
    assert "forks" in str(excinfo.value)


def test_undeterminable_liveness_is_treated_as_live(monkeypatch):
    """`None` is not the empty set, and flattening the two is what would make
    this guard fail open. Every other reader in `discovery` turns an unreadable
    `/proc` into "no agents" — right for a listing, exactly backwards here, where
    "nothing is running" clears the way for the fork.
    """
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: None)
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: pytest.fail("resumed without knowing"))

    with pytest.raises(OwnerError) as excinfo:
        recover(o, unit="set-agent-x.scope", session_id="unknowable", cwd="/tmp")
    assert "cannot determine" in str(excinfo.value)


def test_an_empty_set_of_live_sessions_still_allows_a_resume(monkeypatch):
    """The other direction. A guard that never lets anything through is not a
    guard, and recovery would be impossible.
    """
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    started = {}
    o = AgentOwner()
    monkeypatch.setattr(o, "start", lambda *a, **k: started.update(k) or "ok")

    assert recover(o, unit="set-agent-x.scope", session_id="dead-one", cwd="/tmp") == "ok"
    assert started["resumed_session"] == "dead-one"


def test_the_liveness_check_runs_BEFORE_the_scope_is_stopped(monkeypatch):
    """Order matters and it is not obvious. Stopping first would kill a running
    agent on the way to refusing the resume — a refusal that damages what it was
    protecting.
    """
    events = []
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids",
                        lambda *a, **k: events.append("checked") or {"live-one"})
    monkeypatch.setattr(scopes_backend, "get",
                        lambda u: Scope(unit=u, pid=1, pids=[1], cgroup="/x", active=True, state="active"))
    monkeypatch.setattr(scopes_backend, "stop", lambda *a, **kw: events.append("stopped") or True)

    with pytest.raises(OwnerError):
        recover(AgentOwner(), unit="set-agent-x.scope", session_id="live-one", cwd="/tmp")
    assert events == ["checked"], "the scope must not be stopped on the way to a refusal"


# --------------------------------------------------------------------------- #
# lifecycle logging — task 5.6
# --------------------------------------------------------------------------- #

def test_an_exit_status_is_logged_as_a_sentence_not_as_a_packed_number():
    """`waitpid` returns a packed status where 36608 means "the shell below the
    pty saw a SIGTERM", and nothing about the number says so. A log line an
    operator has to decode by hand is a log line they skip — and the point of
    logging the lifecycle is that an orphan is findable from the logs rather than
    only from the screen.
    """
    import signal as _signal
    from set_orch.fleet.owner import _describe_exit

    assert _describe_exit(0) == "exited cleanly"
    assert _describe_exit(_signal.SIGKILL) == "killed by SIGKILL"
    # The measured case: an agent under a pty runs below a shell, so a SIGTERM
    # arrives as exit code 143 rather than as a signalled death.
    assert _describe_exit(36608) == "exited with code 143 (128+SIGTERM)"
    assert _describe_exit(256) == "exited with code 1"


def test_an_unrecognised_status_says_so_rather_than_guessing():
    """A status shape nobody anticipated must report itself as raw, not be
    forced into the nearest familiar sentence.
    """
    from set_orch.fleet.owner import _describe_exit
    assert "raw wait status" in _describe_exit(0x7F)      # stopped, neither exited nor signalled


# --------------------------------------------------------------------------- #
# task 9.11, second half — the SHAPE of the damage, not only the refusal
#
# The four tests above assert that the resume is refused. All four pass on a
# build whose refusal guards the wrong thing, as long as it raises: they check a
# rule, and a rule is a proxy for a harm. This pair drives the SAME code path
# twice, changing only what the liveness reader answers, and reads the harm off
# the transcript afterwards — a parent with two children, where a session has
# exactly one continuation.
#
# Recorded in design §6.1 as seen once by hand. What follows makes it a fixture
# instead of an anecdote, and gives the fork a name that a later reader can
# search for: two leaves under one parent.
# --------------------------------------------------------------------------- #

def _tail_uuid(path):
    import json
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return json.loads(lines[-1])["uuid"] if lines else None


def _append_turn(path, *, uuid, parent):
    """What a session does when it writes a turn: it appends under the tail it
    read. Two processes that read the same tail therefore write the same parent —
    which is the entire mechanism, and why nothing errors."""
    import json
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"uuid": uuid, "parentUuid": parent, "type": "assistant"}) + "\n")


def _forks(path):
    """Parents with more than one child. A healthy transcript has none."""
    import json
    children = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        children.setdefault(rec.get("parentUuid"), []).append(rec["uuid"])
    return {p: kids for p, kids in children.items() if len(kids) > 1}


def _transcript(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text("", encoding="utf-8")
    parent = None
    for i in range(1, 4):
        _append_turn(path, uuid=f"turn-{i}", parent=parent)
        parent = f"turn-{i}"
    return path


def _resuming_owner(monkeypatch, transcript):
    """An owner whose `start` does what a resumed session does first: read the
    transcript's tail and append under it."""
    o = AgentOwner()
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(
        o, "start",
        lambda *a, **k: _append_turn(transcript, uuid="resumed-1", parent=_tail_uuid(transcript)) or "started",
    )
    return o


def test_a_resume_against_a_live_session_forks_its_transcript(tmp_path, monkeypatch):
    """The harm, performed. This is the build the refusal is protecting against —
    one that answers the liveness question wrongly (a unit-based check clears a
    session started by hand, because it has no scope). Nothing raises, nothing
    logs, and the damage is only visible in the file afterwards.
    """
    transcript = _transcript(tmp_path)
    tail_the_original_holds = _tail_uuid(transcript)
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: set())
    o = _resuming_owner(monkeypatch, transcript)

    recover(o, unit="set-agent-x.scope", session_id="live-one", cwd=str(tmp_path))
    # The original is still running and knows nothing about any of this. Its next
    # turn goes under the tail it was holding — the same parent the resume used.
    _append_turn(transcript, uuid="original-4", parent=tail_the_original_holds)

    forks = _forks(transcript)
    assert forks == {"turn-3": ["resumed-1", "original-4"]}, (
        "the forbidden resume did not produce the fork this test exists to show; "
        f"got {forks!r}"
    )


def test_the_refusal_is_what_keeps_the_transcript_single_threaded(tmp_path, monkeypatch):
    """Same fixture, same call, same writer — only the liveness answer differs.

    So the assertion below is about the guard and nothing else: with the session
    known to be live, `recover` never reaches `start`, the second writer never
    exists, and the transcript keeps exactly one leaf. Remove the refusal and this
    test produces the fork from the test above instead.
    """
    transcript = _transcript(tmp_path)
    tail_the_original_holds = _tail_uuid(transcript)
    monkeypatch.setattr(owner_mod.discovery, "live_session_ids", lambda *a, **k: {"live-one"})
    o = _resuming_owner(monkeypatch, transcript)

    with pytest.raises(OwnerError):
        recover(o, unit="set-agent-x.scope", session_id="live-one", cwd=str(tmp_path))
    _append_turn(transcript, uuid="original-4", parent=tail_the_original_holds)

    assert _forks(transcript) == {}, (
        "a fork survived the refusal — the guard let a second writer onto the transcript"
    )
    # And the positive half, so this cannot pass on a transcript nothing wrote to.
    assert _tail_uuid(transcript) == "original-4", (
        "the original's own turn is missing; the fixture proved nothing"
    )


# --------------------------------------------------------------------------- #
# rename — the name is an identity that can change, and nothing else may
# --------------------------------------------------------------------------- #

def test_a_rename_moves_the_name_and_touches_nothing_else(monkeypatch):
    """The property, stated as the absence of every destructive act.

    A test that asserted only "the agent is now held under N" passes on an
    implementation that stops the scope and resumes the session — which is
    exactly the implementation this design exists to avoid, because it takes the
    in-flight turn and the terminal history with it. So the systemd surface is
    replaced with a fail-on-call, and the assertion is that it was never reached.
    """
    o = _owner_with("before")
    agent = o._agents["before"]
    unit_before, pid_before, fd_before = agent.unit, agent.pid, agent.master_fd
    monkeypatch.setattr(scopes_backend, "_systemctl", lambda *a, **k: pytest.fail("a rename must not touch systemd"))
    monkeypatch.setattr(scopes_backend, "start", lambda *a, **k: pytest.fail("a rename must not start a scope"))

    returned = o.rename("before", "after")

    assert returned.label == "after"
    assert set(o._agents) == {"after"}
    assert (returned.unit, returned.pid, returned.master_fd) == (unit_before, pid_before, fd_before)
    assert returned.resumed_session is None, "a rename must not resume anything"


def test_a_renamed_agent_is_still_stopped_by_its_original_unit(monkeypatch):
    """The reason the unit is stored rather than derived.

    `unit_name("after")` is `set-agent-after.scope`, which does not exist. If any
    path re-derived, the stop would act on a unit systemd does not know — and
    that reads, on screen, as the agent being gone.
    """
    stopped = []
    o = _owner_with("before")
    monkeypatch.setattr(scopes_backend, "stop", lambda unit, **k: stopped.append(unit) or True)
    monkeypatch.setattr(scopes_backend, "is_gone", lambda unit: False)
    o.rename("before", "after")

    result = o.stop("after")

    assert stopped == ["set-agent-before.scope"], stopped
    assert result["unit"] == "set-agent-before.scope"
    assert result["found"] is True and result["population"] == STARTED_HERE


def test_the_old_name_stops_resolving_and_does_not_reach_the_agent(monkeypatch):
    """The old label must not stay addressable through a derived unit.

    Without the guard this is not a harmless 404: `unit_name("before")` names the
    unit the RUNNING agent is in, so a stop under the old name would kill it and
    report it as a foreign orphan — the agent stopped under a name nothing holds.
    """
    o = _owner_with("before")
    monkeypatch.setattr(scopes_backend, "stop", lambda unit, **k: pytest.fail("the old name must not stop anything"))
    monkeypatch.setattr(scopes_backend, "is_gone", lambda unit: False)
    o.rename("before", "after")

    with pytest.raises(OwnerError) as excinfo:
        o.stop("before")
    assert "after" in str(excinfo.value)

    with pytest.raises(OwnerError):
        o.write("before", b"hello\n")


def test_a_rename_onto_a_held_name_is_refused_with_the_holder_named():
    """Refused, never derived around — the asymmetry with restore is deliberate.

    A person is looking at the screen here; a name they did not choose appearing
    instead is a false value they have no reason to question.
    """
    o = _owner_with("one")
    o._agents["two"] = owner_mod.OwnedAgent(
        label="two", unit=scopes_mod.unit_name("two"), pid=222, cwd="/tmp", master_fd=-1,
    )
    with pytest.raises(OwnerError) as excinfo:
        o.rename("one", "two")
    assert "222" in str(excinfo.value), "the refusal must name what holds it"
    assert set(o._agents) == {"one", "two"}
    assert o._agents["one"].label == "one"


def test_renaming_to_the_current_name_changes_nothing_and_is_not_an_error():
    o = _owner_with("same")
    assert o.rename("same", "same").label == "same"
    assert set(o._agents) == {"same"}


def test_an_agent_this_owner_does_not_hold_cannot_be_renamed():
    o = _owner_with("mine")
    with pytest.raises(OwnerError) as excinfo:
        o.rename("someone-elses", "new")
    assert "runtime" in str(excinfo.value), "the reason must say whose name it is"


def test_a_nameless_rename_is_refused():
    o = _owner_with("mine")
    for empty in ("", "   "):
        with pytest.raises(OwnerError):
            o.rename("mine", empty)
    assert o._agents["mine"].label == "mine"


# --------------------------------------------------------------------------- #
# Resolving the command in the CHILD's environment — work-cycle-run-visibility §1
#
# The measurement these guard (2026-08-29): `set-work-cycle` exists only in this
# repo's venv, the owner's own PATH does not contain it, and `POST /api/fleet/units`
# therefore could not start a unit at all. What the caller got was NOT a false
# success — it was a four-second wait ending in `did not become active`, a true
# sentence about the symptom that points away from the missing command.
# --------------------------------------------------------------------------- #

def test_resolution_reads_the_environment_it_is_given_and_not_the_process_s_own(monkeypatch):
    """The seam, asserted as a seam.

    ⚠ A test that sets its own `PATH` and then resolves would measure the proxy:
    it cannot tell "resolved against the argument" from "resolved against the
    ambient environment", because in that test the two are the same string. So
    the process's PATH is pointed at a directory where the command IS, and the
    argument at one where it is NOT — and the answer must follow the argument.
    """
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as has, tempfile.TemporaryDirectory() as has_not:
        tool = os.path.join(has, "set-imaginary-tool")
        with open(tool, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(tool, 0o755)

        monkeypatch.setenv("PATH", has)
        assert owner_mod.resolve_in_env("set-imaginary-tool", {"PATH": has}) == tool
        # The ambient PATH still has it. The argument does not. The argument wins.
        assert owner_mod.resolve_in_env("set-imaginary-tool", {"PATH": has_not}) is None
        # And an environment with no PATH at all is an absence, not a fallback.
        assert owner_mod.resolve_in_env("set-imaginary-tool", {}) is None


def test_a_command_carrying_a_path_is_not_looked_up_on_path(tmp_path):
    """`execvp` does not consult PATH for a name containing a separator; nor does this."""
    tool = tmp_path / "tool"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    assert owner_mod.resolve_in_env(str(tool), {"PATH": ""}) == str(tool)
    assert owner_mod.resolve_in_env(str(tmp_path / "absent"), {"PATH": str(tmp_path)}) is None


def test_an_unresolvable_command_is_refused_by_name_before_anything_is_claimed(monkeypatch):
    """The whole of B-105's fix direction, in one assertion set.

    Named, not merely refused: the message must carry the command and the PATH,
    and must NOT carry the scope's wording — a reader who is told the scope did
    not become active goes and looks at systemd.
    """
    claimed = []
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(scopes_backend, "is_gone", lambda u: True)
    # If any of these runs, the refusal came too late.
    #
    # ⚠ The fake returns a NON-ZERO pid on purpose. `pty.fork()` answers 0 in the
    # child, and this owner's child branch execs immediately — so a fake returning
    # 0 makes the test process itself become `systemd-run` the moment the guard
    # stops holding. Measured while mutation-testing this very guard: the run
    # produced one dot and no failure, because pytest had been replaced. A test
    # that cannot survive the mutation it exists to catch proves nothing.
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (claimed.append("fork"), (4243, 0))[1])
    monkeypatch.setattr(scopes_mod, "adopt",
                        lambda *a, **k: claimed.append("adopt") or None)
    monkeypatch.setattr(owner_mod.os, "close", lambda fd: None)
    monkeypatch.setattr(owner_mod.os, "kill", lambda *a: None)
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    o = AgentOwner()
    with pytest.raises(owner_mod.CommandNotResolvable) as exc:
        o.start(["set-definitely-not-a-command", "--flag"],
                label="unit-x", cwd="/tmp", env={"PATH": "/nonexistent"})

    message = str(exc.value)
    assert "set-definitely-not-a-command" in message
    assert "/nonexistent" in message
    assert "did not become active" not in message
    assert claimed == []           # nothing forked, nothing adopted
    assert o._agents == {}         # and no label held
    # A refusal is not a conflict: a caller must be able to tell the two apart
    # without reading the sentence.
    assert isinstance(exc.value, OwnerError)


def test_resolution_runs_after_the_caller_s_env_is_applied_not_before(monkeypatch):
    """`env=` is the only correct seam, so it is the one resolution must see.

    Measured on the parallel provider track: the child env is `os.environ` minus
    every `CLAUDE*` key, then updated from `env=`. A check placed before that
    update would refuse a command the caller had just made reachable.
    """
    seen = {}
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(scopes_backend, "is_gone", lambda u: True)
    monkeypatch.setattr(owner_mod, "resolve_in_env",
                        lambda cmd, env: seen.update(env=env) or "/found")
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (1, 0))
    monkeypatch.setattr(owner_mod, "_reap", lambda pid: None)
    monkeypatch.setattr(scopes_mod, "adopt",
                        lambda *a, **k: Scope(unit="u", pid=1, pids=[1], cgroup="/x", active=True))
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    AgentOwner().start(["thing"], label="unit-y", cwd="/tmp",
                       env={"PATH": "/from-the-caller"})
    assert seen["env"]["PATH"] == "/from-the-caller"


def test_a_child_that_died_is_reported_as_a_child_not_as_a_scope(monkeypatch):
    """The half resolution cannot predict — and the reason 1.5 exists.

    A scope that never became active and a child that died arrive at one `except`.
    Reporting the scope for both is how the caller learns nothing actionable.
    """
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(scopes_backend, "is_gone", lambda u: True)
    monkeypatch.setattr(owner_mod, "resolve_in_env", lambda cmd, env: "/found")
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (4242, 0))
    monkeypatch.setattr(owner_mod.os, "close", lambda fd: None)
    monkeypatch.setattr(owner_mod.os, "kill", lambda *a: None)
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)
    monkeypatch.setattr(scopes_mod, "adopt",
                        lambda *a, **k: (_ for _ in ()).throw(ScopeError("u did not become active")))

    # 127 << 8 is "exited with code 127" — the exec failure the shell reports.
    monkeypatch.setattr(owner_mod, "_reap", lambda pid: 127 << 8)
    with pytest.raises(OwnerError) as exc:
        AgentOwner().start(["thing"], label="unit-z", cwd="/tmp")
    assert "the child exited with code 127" in str(exc.value)
    assert "did not become active" not in str(exc.value)

    # And when the child is STILL ALIVE, the scope really is what failed — the
    # old wording is correct there and must not be replaced by a guess.
    monkeypatch.setattr(owner_mod, "_reap", lambda pid: None)
    with pytest.raises(OwnerError) as exc2:
        AgentOwner().start(["thing"], label="unit-z2", cwd="/tmp")
    assert "did not become active" in str(exc2.value)


def test_the_claude_strip_runs_before_the_caller_s_env_not_after(monkeypatch):
    """The ORDER inside `build_child_env`, held by a test rather than by a comment.

    Reversing the two lines is silent: the caller's key is stripped, nothing
    errors, and the measured consequence is a compaction loop that reads from
    outside as a slow model rather than as a lost variable.
    """
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "inherited-and-must-go")

    env = owner_mod.build_child_env({"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"})

    # Inherited CLAUDE* keys are gone …
    assert "CLAUDECODE" not in env
    # … but the one the CALLER set survives, which only holds if the strip ran first.
    assert env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "900000"
    assert env["TERM"] == "xterm-256color"


def test_build_child_env_with_no_caller_env_strips_and_adds_nothing_else(monkeypatch):
    monkeypatch.setenv("CLAUDE_ANYTHING", "x")
    monkeypatch.setenv("SET_KEEP_ME", "y")
    env = owner_mod.build_child_env()
    assert "CLAUDE_ANYTHING" not in env
    assert env["SET_KEEP_ME"] == "y"


def test_a_failed_start_carries_what_the_child_actually_said(monkeypatch, tmp_path):
    """The engine's own words, off the pty this owner holds — nowhere else.

    Measured 2026-08-29 against the live service: an engine refusing a bad seat
    exits at once, the scope never registers a cgroup, and the caller was told
    "systemd reports no cgroup; cannot verify survival" while the engine's
    explanation sat unread in the terminal. Same class as the refusal B-105 fixed,
    one layer along: a true sentence about the symptom, pointing away from the
    cause.
    """
    import os

    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"\x1b[31mseat 'set-core' does not identify a single agent "
                       b"session\x1b[0m\r\n")
    os.close(write_fd)

    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(scopes_backend, "is_gone", lambda u: True)
    monkeypatch.setattr(owner_mod, "resolve_in_env", lambda cmd, env: "/found")
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (4242, read_fd))
    monkeypatch.setattr(owner_mod.os, "kill", lambda *a: None)
    monkeypatch.setattr(owner_mod, "_reap", lambda pid: 4 << 8)
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)
    monkeypatch.setattr(scopes_mod, "adopt", lambda *a, **k: (_ for _ in ()).throw(
        ScopeError("set-agent-unit-x.scope: systemd reports no cgroup")))

    with pytest.raises(OwnerError) as exc:
        AgentOwner().start(["thing"], label="unit-said", cwd="/tmp")

    message = str(exc.value)
    assert "does not identify a single agent session" in message
    assert "exited with code 4" in message
    # ⚠ Control sequences stripped: they are noise in an error, and one of them
    # can move a reader's cursor when the message is echoed back.
    assert "\x1b[" not in message


def test_draining_happens_before_the_terminal_is_closed(monkeypatch):
    """Order, not intent: after the close there is nothing left to read, and the
    error would be exactly as blind as it was before this existed.
    """
    import inspect

    src = inspect.getsource(AgentOwner.start)
    drain_at = src.index("_drain(master_fd)")
    close_at = src.index("os.close(master_fd)")
    assert drain_at < close_at, "the pty is closed before it is read"
