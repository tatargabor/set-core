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
        lambda env=None: {k: v for k, v in (env or {}).items() if k != "ANTHROPIC_BASE_URL"},
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


def test_the_refusal_names_the_variable_and_never_its_value(monkeypatch, _nothing_running):
    """A resolved environment carries credentials; this message reaches a log.

    The same class as the masking defect measured on 2026-08-29: a message that
    is helpful about the wrong half.
    """
    monkeypatch.setattr(owner_mod, "build_child_env", lambda env=None: {})
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
                        lambda env=None: {"ANTHROPIC_BASE_URL": "https://somewhere.else"})
    monkeypatch.setattr(owner_mod.pty, "fork", lambda: (4243, 0))
    monkeypatch.setattr(AgentOwner, "_set_window", lambda *a, **k: None)

    with pytest.raises(EnvironmentNotDelivered) as exc:
        AgentOwner().start(["claude"], label="unit-p3", cwd="/tmp",
                           env={"ANTHROPIC_BASE_URL": "https://example.invalid"})
    assert "ANTHROPIC_BASE_URL" in str(exc.value)


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
