"""The owner's provider-aware half — tasks 6.4 onwards.

A separate file from `test_fleet_owner.py` on purpose: two tracks are editing
`owner.py` at the same time, and one shared test file is where their edits would
collide silently. The fixtures below are duplicated from that file rather than
imported for the same reason — a shared fixture module is a third file both
tracks would have to agree on.
"""

from __future__ import annotations

import pytest

from set_orch.fleet import owner as owner_mod
from set_orch.fleet import scopes as scopes_mod
from set_orch.fleet.scopes import _systemd as scopes_backend
from set_orch.fleet.owner import (
    AgentOwner,
    EnvironmentNotDelivered,
    assert_env_survived,
)


@pytest.fixture(autouse=True)
def _pin_the_systemd_backend(monkeypatch):
    """Pin the backend, exactly as the sibling file does and for its reason.

    Without it this file tests whichever backend the developer's platform picks,
    which is green on Linux and a pile of false failures on macOS.
    """
    monkeypatch.setattr(scopes_mod, "_backend", scopes_backend)


@pytest.fixture
def _nothing_running(monkeypatch):
    monkeypatch.setattr(scopes_backend, "get", lambda u: None)
    monkeypatch.setattr(scopes_backend, "is_gone", lambda u: True)


# --------------------------------------------------------------------------- #
# 6.4 — the pre-fork survival guard
# --------------------------------------------------------------------------- #

# AC-48
def test_a_resolved_variable_lost_by_the_builder_stops_the_start(monkeypatch, _nothing_running):
    """The guard's OWN test: it mutates the builder, not the order.

    ⚠ This is deliberately not "reverse the two lines in `build_child_env`".
    That mutation is already caught by the ordering test, and a mutation two
    guards both answer proves neither of them — the same shape measured on
    2026-08-29, where a file's `0600` was set by an `os.open` mode AND a `chmod`,
    so breaking one was silent. Here the builder is replaced wholesale, which
    only this guard can see.
    """
    claimed = []
    # A builder that drops one resolved key and keeps the rest — the silent
    # failure this guard exists for. Nothing about the returned env looks wrong.
    monkeypatch.setattr(
        owner_mod, "build_child_env",
        lambda env=None, unset=None: {k: v for k, v in (env or {}).items()
                                     if k != "ANTHROPIC_BASE_URL"},
    )
    # ⚠ NON-ZERO pid. `pty.fork()` answers 0 in the child and this owner's child
    # branch execs at once, so a fake returning 0 turns the test process itself
    # into the child the moment the guard stops holding: one passing dot, zero
    # failures, and it reads exactly like a test that does not catch the mutation
    # (task 6.3a — measured by a peer on this module the same day).
    monkeypatch.setattr(owner_mod.pty, "fork",
                        lambda: (claimed.append("fork"), (4243, 0))[1])
    monkeypatch.setattr(scopes_mod, "adopt",
                        lambda *a, **k: claimed.append("adopt") or None)
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    with pytest.raises(EnvironmentNotDelivered) as exc:
        AgentOwner().start(
            ["claude"], label="unit-p1", cwd="/tmp",
            env={"ANTHROPIC_BASE_URL": "https://example.invalid",
                 "ANTHROPIC_AUTH_TOKEN": "s3cret-value"},
        )

    assert "ANTHROPIC_BASE_URL" in str(exc.value)
    # No process was created. This is the half that makes the guard a guard
    # rather than a log line.
    assert claimed == [], f"the start proceeded past the guard: {claimed}"


# AC-55
def test_the_refusal_names_the_variable_and_never_its_value(monkeypatch, _nothing_running):
    """A resolved environment carries credentials; this message reaches a log.

    The same class as the masking defect measured on 2026-08-29: a message that
    is helpful about the wrong half.
    """
    monkeypatch.setattr(owner_mod, "build_child_env", lambda env=None, unset=None: {})
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (4243, 0))
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    with pytest.raises(EnvironmentNotDelivered) as exc:
        AgentOwner().start(["claude"], label="unit-p2", cwd="/tmp",
                           env={"ANTHROPIC_AUTH_TOKEN": "s3cret-value"})

    message = str(exc.value)
    assert "ANTHROPIC_AUTH_TOKEN" in message
    assert "s3cret-value" not in message


def test_an_altered_value_counts_as_lost(monkeypatch, _nothing_running):
    """Present-but-wrong is the worse half: the agent starts and runs on the
    wrong endpoint, which no later check distinguishes from the right one."""
    monkeypatch.setattr(owner_mod, "build_child_env",
                        lambda env=None, unset=None: {"ANTHROPIC_BASE_URL": "https://somewhere.else"})
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (4243, 0))
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    with pytest.raises(EnvironmentNotDelivered) as exc:
        AgentOwner().start(["claude"], label="unit-p3", cwd="/tmp",
                           env={"ANTHROPIC_BASE_URL": "https://example.invalid"})
    assert "ANTHROPIC_BASE_URL" in str(exc.value)


# AC-49
def test_a_complete_environment_passes_the_guard(monkeypatch, _nothing_running):
    """The other direction. A guard that refuses everything also passes the
    three tests above, and this is the only assertion that separates the two."""
    reached = []
    monkeypatch.setattr(owner_mod.pty, "fork",
                        lambda: (reached.append("fork"), (4243, 0))[1])
    monkeypatch.setattr(owner_mod, "resolve_in_env", lambda cmd, env: "/usr/bin/claude")
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)
    monkeypatch.setattr(
        scopes_mod, "adopt",
        lambda *a, **k: scopes_mod.Scope(unit="u", pid=4243, cgroup="/c", active=True),
    )

    AgentOwner().start(["claude"], label="unit-p4", cwd="/tmp",
                       env={"ANTHROPIC_BASE_URL": "https://example.invalid"})
    assert reached == ["fork"]


def test_the_guard_compares_against_the_env_about_to_be_used(monkeypatch):
    """Unit-level: the comparison reads the CHILD env, not the input mapping.

    Comparing the input to itself passes whatever the builder did with it — the
    "measure a proxy instead of the thing" class, in the direction that passes.
    """
    assert_env_survived({"A": "1"}, {"A": "1", "B": "2"})       # superset is fine
    with pytest.raises(EnvironmentNotDelivered):
        assert_env_survived({"A": "1"}, {"A": "1", "C": "3", "B": "2"} | {"A": "9"})
    with pytest.raises(EnvironmentNotDelivered):
        assert_env_survived({"A": "1"}, {})
    assert_env_survived({}, {})                                  # nothing resolved, nothing to lose


def test_a_key_the_provider_re_supplies_is_not_required_absent():
    """`unset` means "cleared BEFORE `env` is applied", never "absent from the child".

    Measured 2026-08-29 from a real refusal on the fleet screen: EVERY glm start
    failed, because `FOREIGN_KEYS` strips `ANTHROPIC_AUTH_TOKEN` and
    `ANTHROPIC_BASE_URL` unconditionally and the glm plan then supplies both — so
    the guard demanded a key be absent that the plan requires present. The two
    rules in this one function contradicted each other for any provider that
    carries a credential, which is every provider that needs one.

    Why no test saw it: the fixture in this file uses
    `unset=("ANTHROPIC_API_KEY",)`, which does not overlap its `env`. The real
    constant necessarily does. A fixture that avoids the overlap cannot fail on it.

    Narrowing the removal check loses NO coverage: a key present in `resolved` is
    still checked by the first rule, and more strictly — exact value, not mere
    absence.
    """
    resolved = {"ANTHROPIC_AUTH_TOKEN": "glm-token",
                "ANTHROPIC_BASE_URL": "https://gw.invalid"}
    unset = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    child = dict(resolved)

    assert_env_survived(resolved, child, unset)          # must NOT raise

    # The removal half still bites for a key the plan does NOT re-supply.
    with pytest.raises(EnvironmentNotDelivered):
        assert_env_survived(resolved, child | {"ANTHROPIC_API_KEY": "leftover"}, unset)

    # And a re-supplied key carrying the AMBIENT value is still caught — this is
    # the case the removal check existed for, and it stays covered.
    with pytest.raises(EnvironmentNotDelivered):
        assert_env_survived(resolved, child | {"ANTHROPIC_AUTH_TOKEN": "ambient"}, unset)


def test_the_real_foreign_keys_overlap_a_credentialled_env(monkeypatch):
    """Anchored on the REAL constant, so the fixture cannot drift away from it again.

    The assertion that matters is the first one: if `FOREIGN_KEYS` ever stops
    overlapping a provider env, this test says so instead of going quietly green
    on a case that no longer exists.
    """
    from set_orch.providers.resolver import FOREIGN_KEYS

    env = {"ANTHROPIC_AUTH_TOKEN": "t", "ANTHROPIC_BASE_URL": "https://u.invalid"}
    assert set(FOREIGN_KEYS) & set(env), "fixture drifted from the real constant"

    child = owner_mod.build_child_env(env=env, unset=FOREIGN_KEYS)
    assert_env_survived(env, child, FOREIGN_KEYS)


# --------------------------------------------------------------------------- #
# 6.5 / 6.6 — provider and model across the socket, resolved on the owner's side
# --------------------------------------------------------------------------- #

import asyncio

from set_orch.fleet import ownerd as ownerd_mod
from set_orch.fleet.owner_client import OwnerClient, OwnerClientError
from set_orch.providers.resolver import (
    LEVEL_DEFAULT, LEVEL_PROJECT, LEVEL_REQUEST, LaunchPlan,
)


def _plan(**over) -> LaunchPlan:
    base = dict(
        provider="glm",
        model="glm-4.6",
        env={"ANTHROPIC_BASE_URL": "https://gateway.invalid",
             "ANTHROPIC_AUTH_TOKEN": "s3cret-value"},
        unset=("ANTHROPIC_API_KEY",),
        args=("--setting", "x"),
        provenance={"provider": LEVEL_REQUEST, "model": LEVEL_PROJECT,
                    "credential": LEVEL_DEFAULT},
    )
    base.update(over)
    return LaunchPlan(**base)


class _FakeOwner:
    """Records what `start` was actually handed. Nothing forks."""

    def __init__(self):
        self.calls = []

    def owned(self):
        return []

    def start(self, argv, **kw):
        self.calls.append({"argv": list(argv), **kw})
        return owner_mod.OwnedAgent(
            label=kw["label"], unit=scopes_mod.unit_name(kw["label"]),
            pid=4243, cwd=kw["cwd"], master_fd=-1,
        )


def _run(coro):
    """Own loop, closed here. The sibling file measured why an ambient one is
    not safe: pending handler cleanups run from the garbage collector and are
    reported against whichever unrelated test happens to be running."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _daemon(monkeypatch, tmp_path, plan=None, owner=None):
    owner = owner or _FakeOwner()
    daemon = ownerd_mod.OwnerDaemon(str(tmp_path / "owner.sock"), owner=owner)
    monkeypatch.setattr(daemon, "_attach_drain", lambda agent: None)
    if plan is not None:
        monkeypatch.setattr(ownerd_mod.providers, "resolve",
                            lambda **kw: (recorded.update(kw), plan)[1])
    return daemon, owner


recorded: dict = {}


# AC-42
def test_a_start_naming_a_provider_resolves_it_on_the_owner_s_side(monkeypatch, tmp_path):
    """The names cross the socket; the credential is fetched behind it.

    This is the confidentiality boundary in one assertion: what the caller sent
    is checked to be names only, and the token appears solely in what the owner
    handed to `start`.
    """
    recorded.clear()
    daemon, owner = _daemon(monkeypatch, tmp_path, plan=_plan())

    payload = _run(daemon._do_start({
        "label": "a1", "cwd": "/tmp", "provider": "glm",
        "model": "glm-4.6", "project": "some-project",
    }))

    assert recorded == {"project": "some-project", "provider": "glm", "model": "glm-4.6"}
    call = owner.calls[0]
    assert call["env"]["ANTHROPIC_AUTH_TOKEN"] == "s3cret-value"
    assert call["unset"] == ("ANTHROPIC_API_KEY",)
    # 6.6: the resolved argv extras are appended to the default, not instead of it.
    assert call["argv"] == ["claude", "--dangerously-skip-permissions", "--setting", "x"]
    # The answer carries the provenance and NOT the environment.
    assert payload["provider"] == "glm"
    assert payload["model"] == "glm-4.6"
    assert payload["provenance"]["model"] == LEVEL_PROJECT
    assert "s3cret-value" not in str(payload)
    assert "env" not in payload


# AC-43
def test_a_start_naming_nothing_does_not_resolve_at_all(monkeypatch, tmp_path):
    """The other direction, and it is not cosmetic: an unconditional resolve
    would make every plain start fail on a machine with no providers file —
    turning a new feature into a regression of the existing one."""
    daemon, owner = _daemon(monkeypatch, tmp_path)
    monkeypatch.setattr(ownerd_mod.providers, "resolve",
                        lambda **kw: pytest.fail("resolved without being asked"))

    payload = _run(daemon._do_start({"label": "a2", "cwd": "/tmp"}))

    assert owner.calls[0]["argv"] == ["claude", "--dangerously-skip-permissions"]
    assert owner.calls[0]["env"] is None
    assert "provider" not in payload


def test_the_resolver_outranks_a_caller_supplied_mapping(monkeypatch, tmp_path):
    """A merge where the caller could win would let a request point a named
    provider at another endpoint — and the payload would still say the
    provider's name, so the record would be a false value."""
    recorded.clear()
    daemon, owner = _daemon(monkeypatch, tmp_path, plan=_plan())

    _run(daemon._do_start({
        "label": "a3", "cwd": "/tmp", "provider": "glm",
        "env": {"ANTHROPIC_BASE_URL": "https://attacker.invalid", "KEEP": "me"},
    }))

    env = owner.calls[0]["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://gateway.invalid"
    assert env["KEEP"] == "me"      # unrelated keys are not discarded


def test_the_client_sends_names_and_never_a_credential(monkeypatch):
    """The client half of 6.5, asserted on the WIRE PARAMS rather than on the
    call signature — a named parameter that never reaches the request is exactly
    the shape that passes a signature test and delivers nothing."""
    sent = {}
    client = OwnerClient.__new__(OwnerClient)
    # The owner declares it can resolve — otherwise the client refuses before
    # sending anything, which is B-110's guard doing its job.
    monkeypatch.setattr(OwnerClient, "health",
                        lambda self: {"ok": True, "features": ["provider-selection"]})
    monkeypatch.setattr(OwnerClient, "request",
                        lambda self, method, params=None: sent.update(
                            {"method": method, "params": params or {}}) or {})

    client.start(label="a4", cwd="/tmp", provider="glm", model="glm-4.6",
                 project="p")

    assert sent["method"] == "start"
    assert sent["params"]["provider"] == "glm"
    assert sent["params"]["model"] == "glm-4.6"
    assert sent["params"]["project"] == "p"
    # Named-only: the client offers no way to hand over a resolved credential.
    assert "env" not in sent["params"]


# --------------------------------------------------------------------------- #
# 6.7 / 6.8 / 6.9 — the record, the resume, and what "unrecorded" means
# --------------------------------------------------------------------------- #

from set_orch.fleet import provider_record


# AC-50 / AC-52
def test_the_record_survives_a_restart_of_the_owning_service(monkeypatch, tmp_path):
    """6.8's actual claim, and the only way to test it: the in-memory holder is
    THROWN AWAY between the write and the read.

    A test that wrote and read through one daemon instance would prove the
    dictionary works, which is not the question — the question is what happens
    after `systemctl restart`, while the agent it started is still alive.
    """
    recorded.clear()
    store = str(tmp_path / "fleet-providers.json")
    monkeypatch.setattr(provider_record, "default_record_path", lambda: store)

    daemon, owner = _daemon(monkeypatch, tmp_path, plan=_plan())
    _run(daemon._do_start({"label": "a5", "cwd": "/tmp", "provider": "glm"}))

    # The service dies here. Everything it held goes with it.
    del daemon, owner

    survivor = provider_record.get("set-agent-a5.scope")
    assert survivor["provider"] == "glm"
    assert survivor["model"] == "glm-4.6"
    assert survivor["provenance"]["model"] == LEVEL_PROJECT
    # …and nothing secret came along for the ride.
    assert "s3cret-value" not in pathlib.Path(store).read_text()
    assert "ANTHROPIC_AUTH_TOKEN" not in pathlib.Path(store).read_text()


# AC-3
def test_a_recovery_resumes_on_the_provider_the_session_was_started_on(monkeypatch, tmp_path):
    """6.7. Until 2026-08-29 `recover()` passed no environment at all, so a
    resumed agent came back on the ambient default — a different account, with
    the same label and the same transcript, and nothing saying so."""
    store = str(tmp_path / "fleet-providers.json")
    monkeypatch.setattr(provider_record, "default_record_path", lambda: store)
    provider_record.record("set-agent-a6.scope", provider="glm", model="glm-4.6",
                           provenance={"provider": LEVEL_REQUEST})

    asked = {}
    monkeypatch.setattr(ownerd_mod.providers, "resolve",
                        lambda **kw: (asked.update(kw), _plan())[1])
    passed = {}
    monkeypatch.setattr(ownerd_mod, "recover",
                        lambda owner, **kw: passed.update(kw) or owner_mod.OwnedAgent(
                            label="a6", unit="set-agent-a6.scope", pid=1, cwd="/tmp",
                            master_fd=-1))
    daemon, _ = _daemon(monkeypatch, tmp_path)

    payload = _run(daemon._do_recover({
        "unit": "set-agent-a6.scope", "session_id": "sess-1", "cwd": "/tmp",
    }))

    # Resolved from the RECORD, not from the caller — the caller named neither.
    assert asked == {"provider": "glm", "model": "glm-4.6"}
    assert passed["env"]["ANTHROPIC_AUTH_TOKEN"] == "s3cret-value"
    assert passed["unset"] == ("ANTHROPIC_API_KEY",)
    assert passed["resume_argv"][-2:] == ["--setting", "x"]
    assert "--resume" in passed["resume_argv"]
    assert payload["provider"] == "glm"


# AC-4
def test_a_recovery_with_no_record_resolves_nothing(monkeypatch, tmp_path):
    """An unrecorded agent must not be resumed on the machine default *by this
    path pretending it knew*. It resumes exactly as it did before the record
    existed — which is a known, documented absence rather than a guess."""
    store = str(tmp_path / "fleet-providers.json")
    monkeypatch.setattr(provider_record, "default_record_path", lambda: store)
    monkeypatch.setattr(ownerd_mod.providers, "resolve",
                        lambda **kw: pytest.fail("resolved for an unrecorded agent"))
    passed = {}
    monkeypatch.setattr(ownerd_mod, "recover",
                        lambda owner, **kw: passed.update(kw) or owner_mod.OwnedAgent(
                            label="a7", unit="set-agent-a7.scope", pid=1, cwd="/tmp",
                            master_fd=-1))
    daemon, _ = _daemon(monkeypatch, tmp_path)

    payload = _run(daemon._do_recover({
        "unit": "set-agent-a7.scope", "session_id": "sess-2", "cwd": "/tmp",
    }))
    assert passed["env"] is None
    assert "provider" not in payload


# AC-51
def test_an_agent_with_no_record_is_listed_as_unrecorded_not_as_the_default(monkeypatch, tmp_path):
    """6.9, and it is the load-bearing one in this block.

    `provider: null` next to `provider_recorded: false` is a gap. The machine
    default in the same slot is a CLAIM — and the claim is about which account is
    being billed, so a wrong one is not a cosmetic defect. A gap is not a zero.
    """
    store = str(tmp_path / "fleet-providers.json")
    monkeypatch.setattr(provider_record, "default_record_path", lambda: store)
    provider_record.record("set-agent-known.scope", provider="glm", model="glm-4.6")

    class _Holder:
        def owned(self):
            return [
                owner_mod.OwnedAgent(label="known", unit="set-agent-known.scope",
                                     pid=1, cwd="/tmp", master_fd=-1),
                owner_mod.OwnedAgent(label="older", unit="set-agent-older.scope",
                                     pid=2, cwd="/tmp", master_fd=-1),
            ]

    daemon = ownerd_mod.OwnerDaemon(str(tmp_path / "o.sock"), owner=_Holder())
    rows = {r["label"]: r for r in _run(daemon._do_list({}))}

    assert rows["known"]["provider_recorded"] is True
    assert rows["known"]["provider"] == "glm"
    assert rows["older"]["provider_recorded"] is False
    assert rows["older"]["provider"] is None
    assert rows["older"]["model"] is None


def test_an_unreadable_record_does_not_veto_a_start(monkeypatch, tmp_path):
    """The record describes a start; letting it refuse one inverts that.

    Fail direction chosen deliberately: an unrecorded running agent is a gap the
    readers already handle, while a start that fails because a JSON file is
    corrupt is a new outage with a confusing cause.
    """
    store = tmp_path / "fleet-providers.json"
    store.write_text("{ this is not json")
    monkeypatch.setattr(provider_record, "default_record_path", lambda: str(store))
    assert provider_record.get("anything") is None

    recorded.clear()
    daemon, owner = _daemon(monkeypatch, tmp_path, plan=_plan())
    payload = _run(daemon._do_start({"label": "a8", "cwd": "/tmp", "provider": "glm"}))
    assert payload["provider"] == "glm"
    assert owner.calls, "the start did not happen"


def test_a_stop_that_found_nothing_leaves_the_record_alone(monkeypatch, tmp_path):
    """A stop for a label nobody holds must not delete a live agent's provenance.

    The unit is derived from the label, so a `stop` on a name that was renamed —
    or never existed — reaches a real unit. Deleting on `found: false` would turn
    a recorded agent into an unrecorded one with no act of anyone's naming it.
    """
    store = str(tmp_path / "fleet-providers.json")
    monkeypatch.setattr(provider_record, "default_record_path", lambda: store)
    provider_record.record("set-agent-ghost.scope", provider="glm", model="glm-4.6")

    class _Holder:
        def owned(self):
            return []

        def stop(self, label):
            return {"label": label, "unit": "set-agent-ghost.scope",
                    "found": False, "gone": True, "population": None}

    daemon = ownerd_mod.OwnerDaemon(str(tmp_path / "o.sock"), owner=_Holder())
    _run(daemon._do_stop({"label": "ghost"}))
    assert provider_record.get("set-agent-ghost.scope") is not None


import pathlib  # noqa: E402  — used by the store-content assertions above


# --------------------------------------------------------------------------- #
# The three gaps the mutation harness found in the block above — written here
# because a mutation that nothing catches is a test that was never written, and
# the assertions it seemed to cover were covering something else.
# --------------------------------------------------------------------------- #

# AC-46
def test_the_resolver_s_removals_actually_leave_the_child_environment(monkeypatch):
    """A foreign credential that SURVIVES is the worst of the three outcomes.

    The agent starts, the transcript looks ordinary, and the inherited endpoint
    redirects the call to another account. Nothing errors — which is why the
    removal is a separate argument rather than something a dict could express.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "inherited-from-the-shell")
    monkeypatch.setenv("CLAUDECODE", "1")

    env = owner_mod.build_child_env(
        {"ANTHROPIC_AUTH_TOKEN": "resolved"}, ("ANTHROPIC_API_KEY",))

    assert "ANTHROPIC_API_KEY" not in env
    assert env["ANTHROPIC_AUTH_TOKEN"] == "resolved"
    assert "CLAUDECODE" not in env


# AC-48
def test_a_removal_the_builder_did_not_perform_stops_the_start(monkeypatch, _nothing_running):
    """The guard's removal half, which the loss half does not cover.

    Measured while mutation-testing this block: deleting the removal half left
    every assertion green, because each existing test asserted only that
    something PRESENT was present. Absence needs its own assertion.
    """
    claimed = []
    monkeypatch.setattr(
        owner_mod, "build_child_env",
        lambda env=None, unset=None: {**(env or {}), "ANTHROPIC_API_KEY": "still-here"},
    )
    monkeypatch.setattr(owner_mod.pty, "fork",
                        lambda: (claimed.append("fork"), (4243, 0))[1])
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    with pytest.raises(EnvironmentNotDelivered) as exc:
        AgentOwner().start(["claude"], label="unit-p5", cwd="/tmp",
                           env={"ANTHROPIC_AUTH_TOKEN": "resolved"},
                           unset=("ANTHROPIC_API_KEY",))

    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert "removed" in str(exc.value)
    assert claimed == []


def test_recover_hands_the_environment_to_the_start_it_performs(monkeypatch):
    """End of the 6.7 chain, and the half the daemon test could not see.

    The daemon test replaces `recover` to observe what it was CALLED with, which
    says nothing about what `recover` then does with it. Measured: dropping
    `env=` from recover's own call to `start` left that test green — the same
    "a filter downstream of a source undoes it" shape, one function along.
    """
    monkeypatch.setattr(owner_mod, "_refuse_if_the_session_is_running", lambda s: None)
    monkeypatch.setattr(owner_mod.scopes, "get", lambda u: None)
    monkeypatch.setattr(owner_mod.scopes, "is_gone", lambda u: True)
    seen = {}

    class _Owner:
        def start(self, argv, **kw):
            seen.update(kw)
            seen["argv"] = list(argv)
            return owner_mod.OwnedAgent(label=kw["label"], unit="u", pid=1,
                                        cwd=kw["cwd"], master_fd=-1)

    owner_mod.recover(
        _Owner(), unit="set-agent-r1.scope", session_id="sess-9", cwd="/tmp",
        env={"ANTHROPIC_AUTH_TOKEN": "resolved"}, unset=("ANTHROPIC_API_KEY",),
    )

    assert seen["env"] == {"ANTHROPIC_AUTH_TOKEN": "resolved"}
    assert seen["unset"] == ("ANTHROPIC_API_KEY",)
    assert seen["resumed_session"] == "sess-9"


# --------------------------------------------------------------------------- #
# 7.3 at the owner — a resolution refusal keeps its class across the wire
# --------------------------------------------------------------------------- #

from set_orch.fleet.protocol import Request
from set_orch.providers.errors import ConfigError, UnknownModel, UnknownProvider


@pytest.mark.parametrize("exc,kind", [
    (UnknownProvider("no provider named 'zzz' is declared"), "unknown-provider"),
    (UnknownModel("glm does not list 'opus'"), "unknown-model"),
    (ConfigError("/x/providers.json is mode 0644"), "provider-config"),
])
# AC-39
def test_a_resolution_refusal_travels_as_a_class_not_as_prose(monkeypatch, tmp_path,
                                                              exc, kind):
    """Without this branch the refusal fell through to the generic handler, lost
    its class, and reached the API as an unclassified refusal — answered with a
    409, the status for "somebody else holds that label". A reader sent to
    change a name that was never the problem is B-105's shape one layer along.
    """
    daemon, _ = _daemon(monkeypatch, tmp_path)
    monkeypatch.setattr(ownerd_mod.providers, "resolve",
                        lambda **kw: (_ for _ in ()).throw(exc))

    response = _run(daemon.dispatch(
        Request(method="start",
                params={"label": "a9", "cwd": "/tmp", "provider": "zzz"}),
        None,
    ))

    assert response.error is not None
    assert response.error_kind == kind
    assert response.result is None


# --------------------------------------------------------------------------- #
# B-110 — an owner that would DROP the provider must refuse, not start
# --------------------------------------------------------------------------- #

def test_an_owner_that_cannot_resolve_a_provider_refuses_the_start(monkeypatch):
    """Reported from the screen: a start naming a provider came up on the machine
    default and its tile read `provider unrecorded`.

    The cause was not a bug in the resolution — it was a daemon nineteen hours
    older than its caller, whose `_do_start` reads a fixed set of keys and drops
    the rest. Nothing errored. The same shape as the HTTP body that accepted an
    unknown field and discarded it, one layer down, and the fix has to live in
    the CLIENT: the old daemon is the one running and cannot be taught.
    """
    asked = []
    client = OwnerClient.__new__(OwnerClient)
    monkeypatch.setattr(OwnerClient, "health",
                        lambda self: {"ok": True, "held": 12})  # no `features`
    monkeypatch.setattr(OwnerClient, "request",
                        lambda self, method, params=None: asked.append(method) or {})

    with pytest.raises(OwnerClientError) as exc:
        client.start(label="a", cwd="/tmp", provider="glm")

    assert exc.value.kind == "owner-too-old"
    # The remedy is named, and it is an OPERATOR's act — not "choose another
    # provider", which is what a 409 would have suggested.
    assert "restart" in str(exc.value)
    assert asked == [], "the start was sent to an owner that would have dropped it"


def test_an_owner_that_declares_the_capability_starts_normally(monkeypatch):
    """The other direction. A guard that refuses everything also passes the test
    above, and this is the only assertion that separates the two."""
    sent = {}
    client = OwnerClient.__new__(OwnerClient)
    monkeypatch.setattr(OwnerClient, "health",
                        lambda self: {"ok": True, "features": ["provider-selection"]})
    monkeypatch.setattr(OwnerClient, "request",
                        lambda self, method, params=None: sent.update(
                            {"method": method, "params": params or {}}) or {})

    client.start(label="a", cwd="/tmp", provider="glm", model="glm-4.6")
    assert sent["params"]["provider"] == "glm"


def test_a_start_naming_no_provider_does_not_ask_the_owner_its_age(monkeypatch):
    """An ordinary start must not pay for a second round trip, and must keep
    working against an owner that answers no features at all."""
    sent = {}
    client = OwnerClient.__new__(OwnerClient)
    monkeypatch.setattr(OwnerClient, "health",
                        lambda self: pytest.fail("health asked for a plain start"))
    monkeypatch.setattr(OwnerClient, "request",
                        lambda self, method, params=None: sent.update(
                            {"method": method, "params": params or {}}) or {})

    client.start(label="a", cwd="/tmp")
    assert sent["method"] == "start"


def test_this_owner_declares_the_capability_it_implements(monkeypatch, tmp_path):
    """The handshake's other half, and the one a refactor would break silently:
    the daemon that HAS the resolution must say so, or every provider start is
    refused against a perfectly good owner."""
    daemon = ownerd_mod.OwnerDaemon(str(tmp_path / "o.sock"), owner=_FakeOwner())
    health = _run(daemon._do_health({}))
    assert "provider-selection" in health["features"]


def test_the_feature_guard_is_reusable_and_names_what_would_be_dropped(monkeypatch):
    """One door, so a second parameter does not grow a second guard that drifts.

    Asked for by the concurrent change, which passes `requested_by` and would
    have the same silent loss — with a worse shape: a dropped origin does not
    leave the record EMPTY, it makes the record say no origin was declared,
    which the design deliberately distinguishes from "unknown". A false value,
    not a gap.
    """
    client = OwnerClient.__new__(OwnerClient)
    monkeypatch.setattr(OwnerClient, "health",
                        lambda self: {"ok": True, "features": ["provider-selection"]})

    client.require_feature("provider-selection", because="the provider")  # declared
    with pytest.raises(OwnerClientError) as exc:
        client.require_feature("unit-origin", because="who asked for the unit")
    assert exc.value.kind == "owner-too-old"
    assert "who asked for the unit" in str(exc.value)
    assert "restart" in str(exc.value)


def test_this_owner_declares_every_parameter_a_caller_may_send(monkeypatch, tmp_path):
    """The list and the code that reads it must not drift apart.

    Held as a test rather than as a convention because the failure is silent in
    exactly one direction: a parameter honoured but NOT declared makes every
    caller refuse against a perfectly capable owner, and a parameter declared
    but not honoured is B-110 with extra steps.
    """
    daemon = ownerd_mod.OwnerDaemon(str(tmp_path / "o.sock"), owner=_FakeOwner())
    features = set(_run(daemon._do_health({}))["features"])
    assert features == {"provider-selection", "unit-origin"}

    import inspect
    src = inspect.getsource(ownerd_mod.OwnerDaemon._do_start)
    # Each declared feature names a parameter this handler actually reads.
    assert 'params.get("provider")' in src
    assert 'params.get("requested_by")' in src
