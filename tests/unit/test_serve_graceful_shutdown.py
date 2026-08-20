"""The dashboard must not wait forever for an in-flight request — B-31.

uvicorn's `timeout_graceful_shutdown` defaults to `None`, meaning *wait for
every running task, with no limit*. Measured on the running service on
2026-08-20: `Stopping…` at 12:36:17, the replacement's `Started` at 12:37:48 —
91 s, which is `TimeoutStopUSec=1min 30s` expiring and systemd sending
`SIGKILL`. The journal states the wait outright: *Waiting for background tasks
to complete*.

Two tests, and the split is the point. The first asserts the VALUE reaches
uvicorn, because a config key that is merely computed protects nothing. The
second asserts the DEFAULT is finite, because the whole defect was an absent
value reading as a safe one.

What this file does NOT claim: that ten seconds is enough for any particular
request. That is a judgement, and it is stated where it is made — in
`cmd_serve` — not asserted here as if it were a fact.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))


class _RecordingUvicorn(types.ModuleType):
    """Stands in for uvicorn, and remembers what Config was asked for."""

    def __init__(self) -> None:
        super().__init__("uvicorn")
        self.config_kwargs: dict = {}
        outer = self

        class Config:
            def __init__(self, app, **kwargs):
                outer.config_kwargs = dict(kwargs)

        class Server:
            def __init__(self, config):
                self.config = config
                self.should_exit = False

            def run(self):
                # The server never actually serves here; the measurement is what
                # it was CONFIGURED with, and running would block the test.
                return None

        self.Config = Config
        self.Server = Server


@pytest.fixture()
def served(monkeypatch):
    """Run `cmd_serve` against a fake uvicorn and hand back what it configured."""
    fake = _RecordingUvicorn()
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    from set_orch import cli

    args = types.SimpleNamespace(port=7999, host="127.0.0.1")
    cli.cmd_serve(args)
    return fake


def test_the_shutdown_timeout_reaches_uvicorn(served, monkeypatch):
    assert "timeout_graceful_shutdown" in served.config_kwargs, (
        "uvicorn was configured without a graceful-shutdown timeout, which means "
        "'wait forever' — the exact shape of B-31"
    )


def test_the_default_is_finite_and_well_under_the_systemd_stop_timeout(served):
    value = served.config_kwargs["timeout_graceful_shutdown"]
    assert value is not None, "None is uvicorn's own 'wait forever'"
    assert 0 < float(value) < 90, (
        f"{value} s must sit inside systemd's TimeoutStopSec (90 s), or the "
        "service is still killed rather than stopped"
    )


def test_the_environment_can_override_it(monkeypatch):
    fake = _RecordingUvicorn()
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    monkeypatch.setenv("SET_WEB_GRACEFUL_TIMEOUT", "3.5")
    from set_orch import cli

    cli.cmd_serve(types.SimpleNamespace(port=7999, host="127.0.0.1"))
    assert fake.config_kwargs["timeout_graceful_shutdown"] == 3.5
