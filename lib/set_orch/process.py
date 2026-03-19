"""Process lifecycle management with identity verification.

Replaces bash `kill -0` patterns with psutil-based PID verification that checks
both process existence AND command line identity, preventing PID recycling bugs.
"""

from __future__ import annotations

import os
import re
import signal
import sys
import time
from dataclasses import dataclass

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class CheckResult:
    """Result of a PID check."""

    alive: bool
    match: bool


@dataclass
class KillResult:
    """Result of a safe kill operation."""

    outcome: str  # "terminated", "killed", "already_dead", "not_matched"
    signal: str  # "SIGTERM", "SIGKILL", "none"


@dataclass
class OrphanInfo:
    """Information about an orphaned process."""

    pid: int
    cmdline: str
    change: str  # extracted change name, or ""


def _read_proc_cmdline(pid: int) -> str | None:
    """Read /proc/<pid>/cmdline on Linux. Returns None on failure."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
        return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
    except (OSError, PermissionError):
        return None


def _get_cmdline_psutil(pid: int) -> str | None:
    """Get process cmdline via psutil. Returns None on failure."""
    if not HAS_PSUTIL:
        return None
    try:
        proc = psutil.Process(pid)
        parts = proc.cmdline()
        return " ".join(parts) if parts else None
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def _pid_exists(pid: int) -> bool:
    """Check if PID exists (equivalent to kill -0)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists but we can't signal it


def _matches_pattern(cmdline: str, pattern: str) -> bool:
    """Check if cmdline contains the expected pattern."""
    return pattern in cmdline


def _extract_change_name(cmdline: str) -> str:
    """Extract --change <name> or --label <name> from cmdline."""
    for flag in ("--change", "--label"):
        match = re.search(rf"{flag}\s+(\S+)", cmdline)
        if match:
            return match.group(1)
    return ""


def check_pid(pid: int, expected_cmdline_pattern: str) -> CheckResult:
    """Check if a PID is alive AND matches the expected command pattern.

    Uses /proc/cmdline (Linux fast path) → psutil → kill -0 fallback chain.
    """
    if pid <= 0:
        return CheckResult(alive=False, match=False)

    if not _pid_exists(pid):
        return CheckResult(alive=False, match=False)

    # Try /proc first (Linux fast path)
    cmdline = _read_proc_cmdline(pid)

    # Try psutil if /proc failed
    if cmdline is None:
        cmdline = _get_cmdline_psutil(pid)

    # If we can't read cmdline at all, conservatively report no match
    if cmdline is None:
        print(
            f"Warning: cannot read cmdline for PID {pid}, assuming no match",
            file=sys.stderr,
        )
        return CheckResult(alive=True, match=False)

    matched = _matches_pattern(cmdline, expected_cmdline_pattern)
    return CheckResult(alive=True, match=matched)


def safe_kill(
    pid: int, expected_cmdline_pattern: str, timeout: int = 10
) -> KillResult:
    """Terminate a process with identity verification before each signal.

    Sequence: verify identity → SIGTERM → wait(timeout) → re-verify → SIGKILL.
    """
    if pid <= 0:
        return KillResult(outcome="already_dead", signal="none")

    # Check if alive and matches
    check = check_pid(pid, expected_cmdline_pattern)
    if not check.alive:
        return KillResult(outcome="already_dead", signal="none")
    if not check.match:
        return KillResult(outcome="not_matched", signal="none")

    # Send SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return KillResult(outcome="already_dead", signal="none")
    except PermissionError:
        return KillResult(outcome="not_matched", signal="none")

    # Wait for process to exit
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_exists(pid):
            return KillResult(outcome="terminated", signal="SIGTERM")
        time.sleep(0.2)

    # Re-verify identity before SIGKILL (PID may have been recycled)
    check = check_pid(pid, expected_cmdline_pattern)
    if not check.alive:
        return KillResult(outcome="terminated", signal="SIGTERM")
    if not check.match:
        # PID recycled — original process is dead, don't kill the new one
        return KillResult(outcome="terminated", signal="SIGTERM")

    # Send SIGKILL
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return KillResult(outcome="terminated", signal="SIGTERM")

    return KillResult(outcome="killed", signal="SIGKILL")


def find_orphans(
    expected_pattern: str, known_pids: set[int]
) -> list[OrphanInfo]:
    """Find processes matching pattern whose PIDs are not in the known set.

    Uses psutil to scan all running processes. Falls back to /proc scanning
    on Linux if psutil is unavailable.
    """
    orphans: list[OrphanInfo] = []

    if HAS_PSUTIL:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                pid = proc.info["pid"]
                parts = proc.info["cmdline"]
                if not parts:
                    continue
                cmdline = " ".join(parts)
                if expected_pattern in cmdline and pid not in known_pids:
                    orphans.append(OrphanInfo(
                        pid=pid,
                        cmdline=cmdline,
                        change=_extract_change_name(cmdline),
                    ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return orphans

    # Fallback: scan /proc on Linux
    if sys.platform == "linux":
        try:
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                pid = int(entry)
                if pid in known_pids:
                    continue
                cmdline = _read_proc_cmdline(pid)
                if cmdline and expected_pattern in cmdline:
                    orphans.append(OrphanInfo(
                        pid=pid,
                        cmdline=cmdline,
                        change=_extract_change_name(cmdline),
                    ))
        except OSError:
            pass
        return orphans

    # No psutil, not Linux — can't scan
    print(
        "Warning: psutil not available and not on Linux, cannot scan for orphans",
        file=sys.stderr,
    )
    return orphans
