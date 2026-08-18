"""Unit-test guards that must hold for the whole suite, not per file.

**No unit test may start a real agent session.** The work-cycle engine's `run` path spawns a
full agent session by design — that is the capability. A unit test that reaches it therefore
launches a real model run against a temporary tree, and it was measured doing exactly that:
two of them spawned live sessions and the suite hung for minutes until they were killed by
hand.

Per-file discipline is the wrong fix, because a file added later will not have it. The
fixture below is autouse and suite-wide: the default runner becomes one that FAILS the test,
naming what to do instead. A test that genuinely wants to drive the lifecycle installs its
own fake through `agent_runner`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))


@pytest.fixture(autouse=True)
def _no_real_agent_sessions(monkeypatch):
    """Replace the engine's agent runner with one that refuses, for every unit test."""
    try:
        from set_workcycle import cli
    except Exception:  # pragma: no cover - the package may be absent in a partial checkout
        yield
        return

    def _refuse(prompt, cwd, **kwargs):
        raise AssertionError(
            "a unit test reached the agent-session runner. Unit tests must not spawn a real "
            "session: pass a fake through the `agent_runner` fixture, or use `--dry-run`."
        )

    monkeypatch.setattr(cli, "_AGENT_RUNNER", _refuse, raising=False)
    yield


@pytest.fixture
def agent_runner(monkeypatch):
    """Install a fake agent runner and return a recorder of what it was asked.

    Usage:  ``agent_runner(final_text='```json\\n{...}\\n```')``
    """
    from set_workcycle import cli
    from set_workcycle.runner import AgentRun

    calls: list[dict] = []

    def install(final_text: str = "", *, session_id: str = "sess-test", exit_code: int = 0,
                side_effect=None):
        """`side_effect(cwd)` stands in for the work a real unit would do — marking its
        checkboxes, editing files. Without it a fake unit *claims* completion while the tree
        shows nothing, which is a divergence rather than a run."""
        def fake(prompt, cwd, **kwargs):
            calls.append({"prompt": prompt, "cwd": str(cwd), **kwargs})
            if side_effect is not None:
                side_effect(Path(cwd))
            return AgentRun(session_id=session_id, final_text=final_text,
                            exit_code=exit_code, events=3)

        monkeypatch.setattr(cli, "_AGENT_RUNNER", fake, raising=False)
        return calls

    install.calls = calls  # type: ignore[attr-defined]
    return install
