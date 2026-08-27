"""Run status on a platform without `/proc`.

Before the `macos-fleet-discovery` change `purpose._pid_state()` asked
`os.path.isdir("/proc/<pid>")`, which is False for every pid on a Mac. Measured
2026-08-27 against a live agent at pid 37343: `(False, False)` — so every
recorded run reported `stale`, which is "nothing is running" said about a machine
where something was.

`tests/unit/test_fleet_purpose.py` drives the same code against a fake `/proc`
tree and is untouched; this file is the other backend.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from set_orch.fleet import procsource, purpose
from set_orch.fleet.procsource import _darwin


PS_IDENTITY = (
    "    1     0 /sbin/launchd\n"
    "37343 37323 claude\n"
    " 4242     1 /usr/bin/gedit\n"
)


@pytest.fixture
def on_macos(monkeypatch):
    monkeypatch.setattr(procsource, "BACKEND", "darwin")
    monkeypatch.setattr(
        _darwin.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, PS_IDENTITY, ""),
    )


def _record(tmp_path, unit, **fields):
    d = tmp_path / purpose.RUN_STATE_REL / "demo"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{unit}.json").write_text(json.dumps({"change": "demo", "unit_id": unit, **fields}))


def _one(tmp_path, unit):
    return [p for p in purpose.read_purposes(str(tmp_path), with_progress=False)
            if p.unit_id == unit][0]


def test_a_live_agent_pid_is_running_rather_than_stale(tmp_path, on_macos):
    _record(tmp_path, "u1", pid=37343)
    got = _one(tmp_path, "u1")
    assert got.status == "running"
    assert got.pid_unverified is False


def test_a_live_pid_that_is_not_an_agent_is_running_but_unverified(tmp_path, on_macos):
    """A pid is recycled. "A process holds that number" is not "your run is
    alive", and collapsing the two would let a stale record borrow a stranger."""
    _record(tmp_path, "u2", pid=4242)
    got = _one(tmp_path, "u2")
    assert got.status == "running"
    assert got.pid_unverified is True


def test_a_pid_that_is_gone_is_stale(tmp_path, on_macos):
    _record(tmp_path, "u3", pid=999999)
    assert _one(tmp_path, "u3").status == "stale"


def test_a_committed_run_is_finished_without_consulting_the_pid(tmp_path, monkeypatch, on_macos):
    """Finished first, because a committed run is finished whatever its pid now
    belongs to — asking about the pid first would call every completed run stale
    as soon as its process exited, which is always."""
    _record(tmp_path, "u4", pid=999999, commit="abc123")
    monkeypatch.setattr(
        _darwin, "read_table",
        lambda: pytest.fail("a finished run must not consult the process table"),
    )
    assert _one(tmp_path, "u4").status == "finished"


def test_the_process_table_is_read_once_for_a_whole_directory_of_records(tmp_path, on_macos, monkeypatch):
    """One `ps` for the directory, not one per record. On `/proc` this is the same
    listing it always was."""
    for n in range(5):
        _record(tmp_path, f"m{n}", pid=37343)
    reads = []
    real = _darwin.read_table
    monkeypatch.setattr(_darwin, "read_table", lambda: (reads.append(1), real())[1])

    purpose.read_purposes(str(tmp_path), with_progress=False)

    assert len(reads) == 1, f"the table was read {len(reads)} times for 5 records"


def test_an_unreadable_table_does_not_claim_a_run_is_running(tmp_path, on_macos, monkeypatch):
    """The direction that matters here is the opposite of the listing's: claiming
    a run is alive on a reading that failed would hide a stale record forever."""
    monkeypatch.setattr(
        _darwin.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", "ps: illegal option"),
    )
    _record(tmp_path, "u5", pid=37343)
    assert _one(tmp_path, "u5").status == "stale"
