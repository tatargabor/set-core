"""Reading the waiter processes without `/proc`.

The distinction every test here defends is between "measured, none found" and
"could not measure". They lead to opposite actions — an empty list invites
installing a waiter, an unreadable table invites doing nothing — and macOS spent
its whole life on the second answer because the reader walked `/proc`
unconditionally. A permanent unknown is not a safe default; it is a screen that
can never be acted on.
"""
from __future__ import annotations

import subprocess

import pytest

from set_orch.fleet import instruct

WAITER = "/usr/bin/node /opt/sac/sac.mjs wait room-a room-b"


def _ps(stdout: str, returncode: int = 0):
    return lambda *a, **k: subprocess.CompletedProcess(a[0], returncode, stdout, "")


@pytest.fixture
def on_macos(monkeypatch):
    monkeypatch.setattr(instruct.sys, "platform", "darwin")


# --- the platform choice --------------------------------------------------- #

def test_macos_returns_a_measurement_rather_than_a_permanent_failure(on_macos, monkeypatch):
    """AC-20. Before the split this returned None on every Mac, forever."""
    monkeypatch.setattr(instruct.subprocess, "run", _ps(f"  4242 {WAITER}\n"))
    monkeypatch.setattr(instruct, "_ps_session", lambda pid: "sess-1")
    monkeypatch.setattr(instruct, "_ps_cwd", lambda pid: "/work")

    waiters = instruct.live_waiters()

    assert waiters is not None, "macOS still reports that it could not measure"
    assert [w.pid for w in waiters] == [4242]
    assert waiters[0].rooms == ("room-a", "room-b")


def test_a_genuinely_empty_machine_is_reported_as_measured(on_macos, monkeypatch):
    """AC-23. An empty list and a failure to look are different answers."""
    monkeypatch.setattr(instruct.subprocess, "run", _ps("  1 /sbin/launchd\n  2 /usr/sbin/syslogd\n"))

    assert instruct.live_waiters() == []


def test_an_unreadable_process_table_is_reported_as_such(on_macos, monkeypatch):
    """AC-22. `None`, never `[]` — the caller renders one as "nothing is known"."""
    def boom(*a, **k):
        raise OSError("ps: command not found")
    monkeypatch.setattr(instruct.subprocess, "run", boom)

    assert instruct.live_waiters() is None


def test_a_failing_ps_is_not_read_as_an_empty_machine(on_macos, monkeypatch):
    """`ps` exiting non-zero with empty stdout would parse to zero waiters. That
    is the widening this capability exists to prevent, arriving through a
    returncode nobody checked."""
    monkeypatch.setattr(instruct.subprocess, "run", _ps("", returncode=1))

    assert instruct.live_waiters() is None


def test_an_explicit_proc_root_still_reads_that_tree_on_macos(on_macos, tmp_path):
    """The switch is by platform, but an explicit root wins — which is how the
    Linux behaviour stays testable from any machine."""
    assert instruct.live_waiters(proc_root=str(tmp_path)) == []


def test_linux_does_not_reach_for_ps(monkeypatch, tmp_path):
    """AC-21. The Linux path must not change shape because a second one appeared."""
    monkeypatch.setattr(instruct.sys, "platform", "linux")
    def fail(*a, **k):
        pytest.fail("the Linux reader must not shell out to ps")
    monkeypatch.setattr(instruct.subprocess, "run", fail)

    assert instruct.live_waiters(proc_root=str(tmp_path)) == []


# --- fields the platform will not give ------------------------------------- #

def test_a_waiter_with_an_unreadable_working_directory_is_still_listed(on_macos, monkeypatch):
    """AC-24. Dropping it would be a live process the surface stops accounting
    for — the same false absence, reached through a missing field."""
    monkeypatch.setattr(instruct.subprocess, "run", _ps(f"  4242 {WAITER}\n"))
    monkeypatch.setattr(instruct, "_ps_session", lambda pid: "sess-1")
    monkeypatch.setattr(instruct, "_ps_cwd", lambda pid: None)

    waiters = instruct.live_waiters()

    assert len(waiters) == 1, "a waiter was dropped for a field that could not be read"
    assert waiters[0].cwd is None


def test_an_unknown_session_is_absent_not_guessed(on_macos, monkeypatch):
    """AC-25. `session_known` is what decides whether a waiter may be removed, so
    a plausible default here is how a live waiter gets killed."""
    monkeypatch.setattr(instruct.subprocess, "run", _ps(f"  4242 {WAITER}\n"))
    monkeypatch.setattr(instruct, "_ps_session", lambda pid: None)
    monkeypatch.setattr(instruct, "_ps_cwd", lambda pid: "/work")

    waiter = instruct.live_waiters()[0]

    assert waiter.session is None
    assert waiter.session_known is False


# --- the per-waiter lookups ------------------------------------------------ #

def test_the_session_is_taken_from_the_processs_own_environment(monkeypatch):
    monkeypatch.setattr(
        instruct.subprocess, "run",
        _ps("node sac.mjs wait PATH=/usr/bin CLAUDE_CODE_SESSION_ID=abc-123 TERM=xterm\n"),
    )
    assert instruct._ps_session(4242) == "abc-123"


def test_an_environment_without_the_marker_yields_no_session(monkeypatch):
    monkeypatch.setattr(instruct.subprocess, "run", _ps("node sac.mjs wait PATH=/usr/bin\n"))
    assert instruct._ps_session(4242) is None


def test_the_cwd_comes_from_lsofs_machine_readable_output(monkeypatch):
    monkeypatch.setattr(instruct.subprocess, "run", _ps("p4242\nfcwd\nn/Users/x/work\n"))
    assert instruct._ps_cwd(4242) == "/Users/x/work"


def test_a_missing_lsof_degrades_one_field_and_nothing_else(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("lsof")
    monkeypatch.setattr(instruct.subprocess, "run", boom)
    assert instruct._ps_cwd(4242) is None


def test_the_cwd_lookup_is_not_run_for_every_process(on_macos, monkeypatch):
    """`lsof` over a whole process table is a syscall sweep, and this runs on the
    fleet's polling path. Only the lines that already matched may pay for it."""
    table = "\n".join([f"  {n} /usr/bin/some-daemon" for n in range(100, 200)])
    monkeypatch.setattr(instruct.subprocess, "run", _ps(table + f"\n  4242 {WAITER}\n"))
    looked_up = []
    monkeypatch.setattr(instruct, "_ps_cwd", lambda pid: looked_up.append(pid))
    monkeypatch.setattr(instruct, "_ps_session", lambda pid: None)

    instruct.live_waiters()

    assert looked_up == [4242], f"cwd was looked up for {len(looked_up)} processes"


# --- session liveness, the second gate on `measured` ------------------------ #

def test_session_liveness_is_measurable_on_macos(monkeypatch):
    """The waiters panel's `measured` flag depends on TWO readers, and fixing one
    left the other answering "undeterminable" forever. Measured end to end
    2026-08-27: the panel still said nothing was known about what was listening,
    with a different reason than before, which is the failure mode of fixing half
    a platform assumption.
    """
    from set_orch.fleet import discovery

    monkeypatch.setattr(discovery.sys, "platform", "darwin")
    monkeypatch.setattr(discovery, "_pids_by_comm_from_ps", lambda name: [4242])
    monkeypatch.setattr(discovery, "_load_session_records",
                        lambda d: {4242: {"sessionId": "abc-123"}})

    assert discovery.live_session_ids() == {"abc-123"}


def test_an_unreadable_table_still_yields_undeterminable_not_empty(monkeypatch):
    """The distinction this reader exists for: an empty set means "go ahead and
    resume", and an unreadable table must never be flattened into it — that
    would resume onto a live session and fork its conversation silently."""
    from set_orch.fleet import discovery

    monkeypatch.setattr(discovery.sys, "platform", "darwin")
    monkeypatch.setattr(discovery, "_pids_by_comm_from_ps", lambda name: None)

    assert discovery.live_session_ids() is None


def test_an_explicit_proc_root_keeps_the_linux_reader_on_macos(monkeypatch, tmp_path):
    from set_orch.fleet import discovery

    monkeypatch.setattr(discovery.sys, "platform", "darwin")
    monkeypatch.setattr(discovery, "_pids_by_comm_from_ps",
                        lambda name: pytest.fail("an explicit proc_root must read that tree"))

    assert discovery.live_session_ids(proc_root=str(tmp_path)) == set()


def test_identity_not_substring(monkeypatch):
    """`ps -o comm=` prints a PATH on macOS, so the basename decides. A shell
    whose command line merely contains the word is not an agent — there were 31
    of those on the machine the Linux reader was measured against."""
    from set_orch.fleet import discovery

    table = (
        "  100 /opt/homebrew/bin/claude\n"
        "  200 /bin/zsh\n"
        "  300 /usr/bin/grep-for-claude\n"
        "  400 claude\n"
    )
    monkeypatch.setattr(
        discovery.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, table, ""),
    )

    assert discovery._pids_by_comm_from_ps("claude") == [100, 400]
