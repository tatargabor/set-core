"""Tests for set_orch.process — PID lifecycle management."""

import os
import signal
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.process import (
    CheckResult,
    KillResult,
    OrphanInfo,
    check_pid,
    find_orphans,
    safe_kill,
    _extract_change_name,
    _pid_exists,
)


class TestCheckPid:
    def test_alive_and_matching(self):
        """Current process should be alive and match 'python'."""
        result = check_pid(os.getpid(), "python")
        assert result.alive is True
        assert result.match is True

    def test_alive_but_not_matching(self):
        """Current process is alive but doesn't match 'nonexistent-binary'."""
        result = check_pid(os.getpid(), "nonexistent-binary-xyz")
        assert result.alive is True
        assert result.match is False

    def test_dead_pid(self):
        """A non-existent PID should return alive=False, match=False."""
        result = check_pid(999999999, "anything")
        assert result.alive is False
        assert result.match is False

    def test_zero_pid(self):
        result = check_pid(0, "anything")
        assert result.alive is False
        assert result.match is False

    def test_negative_pid(self):
        result = check_pid(-1, "anything")
        assert result.alive is False
        assert result.match is False

    def test_init_pid(self):
        """PID 1 should be alive (init/systemd) but not match a random pattern."""
        result = check_pid(1, "set-loop-nonexistent")
        assert result.alive is True
        assert result.match is False


class TestSafeKill:
    def test_terminates_with_sigterm(self):
        """Start a sleep process and verify safe_kill terminates it."""
        proc = subprocess.Popen(["sleep", "60"])
        pid = proc.pid
        time.sleep(0.1)  # let it start
        assert _pid_exists(pid)

        result = safe_kill(pid, "sleep", timeout=5)
        assert result.outcome == "terminated"
        assert result.signal == "SIGTERM"
        proc.wait()  # reap zombie before checking
        assert not _pid_exists(pid)

    def test_already_dead(self):
        """safe_kill on a dead PID returns already_dead."""
        result = safe_kill(999999999, "anything", timeout=1)
        assert result.outcome == "already_dead"
        assert result.signal == "none"

    def test_not_matched(self):
        """safe_kill refuses to kill a process that doesn't match the pattern."""
        proc = subprocess.Popen(["sleep", "60"])
        pid = proc.pid

        result = safe_kill(pid, "nonexistent-pattern-xyz", timeout=1)
        assert result.outcome == "not_matched"
        assert result.signal == "none"

        # Process should still be alive
        assert _pid_exists(pid)
        proc.terminate()
        proc.wait()

    def test_zero_pid(self):
        result = safe_kill(0, "anything", timeout=1)
        assert result.outcome == "already_dead"

    def test_sigkill_escalation(self):
        """Process that ignores SIGTERM should get SIGKILL."""
        # Start a process that traps SIGTERM — use sys.executable so the
        # cmdline pattern matches regardless of which python3 runs the tests
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"]
        )
        pid = proc.pid
        time.sleep(0.3)  # let the signal handler install

        result = safe_kill(pid, "python", timeout=2)
        assert result.outcome == "killed"
        assert result.signal == "SIGKILL"
        proc.wait()  # reap zombie before checking
        assert not _pid_exists(pid)


class TestFindOrphans:
    def test_finds_orphaned_process(self):
        """Start a sleep process and verify find_orphans can find it."""
        proc = subprocess.Popen(["sleep", "60"])
        pid = proc.pid

        orphans = find_orphans("sleep", known_pids=set())
        pids_found = {o.pid for o in orphans}
        assert pid in pids_found

        proc.terminate()
        proc.wait()

    def test_excludes_known_pids(self):
        """Known PIDs should be excluded from orphan results."""
        proc = subprocess.Popen(["sleep", "60"])
        pid = proc.pid

        orphans = find_orphans("sleep", known_pids={pid})
        pids_found = {o.pid for o in orphans}
        assert pid not in pids_found

        proc.terminate()
        proc.wait()

    def test_no_matches(self):
        """No orphans when pattern doesn't match anything."""
        orphans = find_orphans("totally-nonexistent-binary-xyz-12345", known_pids=set())
        assert orphans == []


class TestExtractChangeName:
    def test_extracts_change_flag(self):
        assert _extract_change_name("set-loop start --change my-feature --max 30") == "my-feature"

    def test_extracts_label_flag(self):
        assert _extract_change_name("set-loop start --label add-auth --done openspec") == "add-auth"

    def test_no_flag(self):
        assert _extract_change_name("set-loop start --max 30") == ""

    def test_change_takes_priority(self):
        assert _extract_change_name("set-loop --change foo --label bar") == "foo"
