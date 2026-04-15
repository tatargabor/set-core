"""Test: e2e gate kills stale port listeners before spawning Playwright.

See micro-web / craftbrew run diagnostics: Playwright's webServer start
happens BEFORE globalSetup, so a zombie `next start` from a prior crashed
gate causes "port already used" and Playwright exits with exit_code=1 and
no parseable failure list. The gate's baseline comparison can't save us —
it mis-classifies as "crash or formatter issue", wastes retries.

Fix lives at the gate-runner layer (Python) via lsof + kill.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))
sys.path.insert(0, str(_ROOT / "modules" / "web"))


def test_kill_stale_listeners_invokes_lsof_then_kill():
    from set_project_web.gates import _kill_stale_listeners_on_port

    fake_lsof = subprocess.CompletedProcess(
        args=["lsof"], returncode=0, stdout="12345\n67890\n", stderr="",
    )
    killed: list[int] = []

    def _fake_kill(pid: int, sig: int) -> None:
        killed.append(pid)

    with (
        patch("set_project_web.gates.subprocess.run", return_value=fake_lsof) as run_mock,
        patch("set_project_web.gates.os.kill", side_effect=_fake_kill),
        patch("set_project_web.gates.time.sleep"),  # no real sleep in tests
    ):
        _kill_stale_listeners_on_port(3147)

    assert run_mock.called
    assert sorted(killed) == [12345, 67890]


def test_kill_stale_listeners_noop_when_port_zero():
    from set_project_web.gates import _kill_stale_listeners_on_port

    with patch("set_project_web.gates.subprocess.run") as run_mock:
        _kill_stale_listeners_on_port(0)

    assert not run_mock.called


def test_kill_stale_listeners_survives_missing_lsof():
    from set_project_web.gates import _kill_stale_listeners_on_port

    with patch("set_project_web.gates.subprocess.run", side_effect=FileNotFoundError("lsof")):
        # Must NOT raise — this is best-effort, fatal failure here would
        # break the gate when lsof isn't installed.
        _kill_stale_listeners_on_port(3147)


def test_kill_stale_listeners_handles_no_pids():
    from set_project_web.gates import _kill_stale_listeners_on_port

    empty_lsof = subprocess.CompletedProcess(
        args=["lsof"], returncode=1, stdout="", stderr="",
    )
    killed: list[int] = []
    with (
        patch("set_project_web.gates.subprocess.run", return_value=empty_lsof),
        patch("set_project_web.gates.os.kill", side_effect=lambda pid, sig: killed.append(pid)),
        patch("set_project_web.gates.time.sleep"),
    ):
        _kill_stale_listeners_on_port(3147)

    assert killed == []


def test_kill_stale_listeners_survives_kill_permission_error():
    from set_project_web.gates import _kill_stale_listeners_on_port

    fake_lsof = subprocess.CompletedProcess(
        args=["lsof"], returncode=0, stdout="99999\n", stderr="",
    )
    with (
        patch("set_project_web.gates.subprocess.run", return_value=fake_lsof),
        patch("set_project_web.gates.os.kill", side_effect=ProcessLookupError("no such pid")),
        patch("set_project_web.gates.time.sleep"),
    ):
        # ProcessLookupError is an OSError subclass — must be caught.
        _kill_stale_listeners_on_port(3147)
