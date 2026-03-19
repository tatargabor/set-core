"""Daemon lifecycle: start, stop, status, auto-start, daemonize.

Manages PID files and Unix sockets. Reuses process.py patterns for stale PID detection.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Default paths
SHODH_STORAGE = os.environ.get(
    "SHODH_STORAGE",
    os.path.join(os.environ.get("HOME", ""), ".local", "share", "set-core", "memory"),
)
RUN_DIR = "/tmp"

CMDLINE_PATTERN = "set_memoryd"
STARTUP_TIMEOUT = 5.0  # seconds to wait for daemon to start


@dataclass
class DaemonInfo:
    """Running daemon state."""

    pid: int
    socket_path: str
    pid_path: str
    project: str
    alive: bool


def socket_path_for(project: str) -> str:
    return os.path.join(RUN_DIR, f"wt-memoryd-{project}.sock")


def pid_path_for(project: str) -> str:
    return os.path.join(RUN_DIR, f"wt-memoryd-{project}.pid")


def storage_path_for(project: str) -> str:
    return os.path.join(SHODH_STORAGE, project)


def log_path_for(project: str) -> str:
    log_dir = os.path.join(SHODH_STORAGE, project)
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "wt-memoryd.log")


def _pid_exists(pid: int) -> bool:
    """Check if PID exists (kill -0)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_pid(pid_path: str) -> int:
    """Read PID from file. Returns 0 if unreadable."""
    try:
        with open(pid_path, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def _check_daemon(project: str) -> DaemonInfo:
    """Check if daemon is running for project."""
    sock = socket_path_for(project)
    pidfile = pid_path_for(project)
    pid = _read_pid(pidfile)

    alive = pid > 0 and _pid_exists(pid)

    # Verify it's actually our daemon via /proc/cmdline
    if alive:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmdline = f.read().decode("utf-8", errors="replace")
            if CMDLINE_PATTERN not in cmdline:
                alive = False
        except OSError:
            pass  # can't verify, trust PID

    return DaemonInfo(
        pid=pid, socket_path=sock, pid_path=pidfile,
        project=project, alive=alive,
    )


def is_running(project: str) -> bool:
    """Check if daemon is running for project."""
    info = _check_daemon(project)
    if info.alive:
        return True
    # Stale state — clean up
    if info.pid > 0:
        _cleanup_stale(project)
    return False


def _cleanup_stale(project: str) -> None:
    """Remove stale socket and PID files."""
    for path in (socket_path_for(project), pid_path_for(project)):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def status(project: str) -> dict:
    """Get daemon status."""
    info = _check_daemon(project)
    return {
        "project": project,
        "running": info.alive,
        "pid": info.pid if info.alive else None,
        "socket": info.socket_path,
        "socket_exists": os.path.exists(info.socket_path),
    }


def start(project: str, storage_path: str = "", foreground: bool = False) -> int:
    """Start daemon for project. Returns PID (0 on failure).

    If foreground=True, runs in current process (blocking).
    Otherwise daemonizes via subprocess.
    """
    if is_running(project):
        info = _check_daemon(project)
        return info.pid

    _cleanup_stale(project)

    if not storage_path:
        storage_path = storage_path_for(project)

    sock = socket_path_for(project)
    pidfile = pid_path_for(project)
    logfile = log_path_for(project)

    if foreground:
        # Run directly (blocking) — used by `wt-memoryd run`
        _run_server(project, storage_path, sock, pidfile)
        return os.getpid()

    # Daemonize: spawn detached subprocess
    set_tools_root = _find_set_tools_root()
    shodh_python = _find_shodh_python()

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(set_tools_root, "lib") + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        shodh_python, "-m", "set_memoryd",
        "run", "--project", project,
        "--storage", storage_path,
    ]

    with open(logfile, "a") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # setsid — detach from terminal
            env=env,
        )

    # Wait for socket to appear
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if os.path.exists(sock):
            return proc.pid
        time.sleep(0.05)

    # Startup might be slow (model loading), check PID
    if proc.poll() is None:
        return proc.pid

    return 0


def stop(project: str, timeout: int = 5) -> bool:
    """Stop daemon for project. Returns True if stopped."""
    info = _check_daemon(project)
    if not info.alive:
        _cleanup_stale(project)
        return True

    # Send SIGTERM
    try:
        os.kill(info.pid, signal.SIGTERM)
    except ProcessLookupError:
        _cleanup_stale(project)
        return True

    # Wait for exit
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_exists(info.pid):
            _cleanup_stale(project)
            return True
        time.sleep(0.1)

    # Force kill
    try:
        os.kill(info.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    _cleanup_stale(project)
    return True


def ensure_running(project: str, storage_path: str = "") -> bool:
    """Ensure daemon is running, auto-start if needed. Returns True if running."""
    if is_running(project):
        return True
    pid = start(project, storage_path=storage_path)
    return pid > 0


def _run_server(
    project: str, storage_path: str, socket_path: str, pid_path: str
) -> None:
    """Run the daemon server (blocking). Used for foreground mode."""
    import asyncio
    from .server import MemoryDaemon

    daemon = MemoryDaemon(
        project=project,
        storage_path=storage_path,
        socket_path=socket_path,
        pid_path=pid_path,
    )
    asyncio.run(daemon.run())


def _find_shodh_python() -> str:
    """Find the Python binary that has shodh-memory installed.

    Checks: 1) saved config, 2) current python, 3) sys.executable fallback.
    Mirrors bin/set-common.sh find_shodh_python logic.
    """
    config_file = os.path.join(
        os.environ.get("HOME", ""), ".config", "set-core", "shodh-python"
    )

    # 1. Check saved config (set by wt-memory on first successful use)
    if os.path.isfile(config_file):
        try:
            with open(config_file, "r") as f:
                saved = f.read().strip()
            if saved and os.path.isfile(saved) and os.access(saved, os.X_OK):
                return saved
        except OSError:
            pass

    # 2. Try current Python
    try:
        import shodh_memory  # noqa: F401
        return sys.executable
    except ImportError:
        pass

    # 3. Fallback to sys.executable (will fail at import time in server)
    return sys.executable


def _find_set_tools_root() -> str:
    """Find set-core root directory."""
    # From this file: lib/set_memoryd/lifecycle.py → ../../
    here = Path(__file__).resolve()
    root = here.parent.parent.parent
    if (root / "bin" / "wt-memory").exists():
        return str(root)
    # Fallback: check PATH for wt-memory
    import shutil
    wt_mem = shutil.which("wt-memory")
    if wt_mem:
        return str(Path(wt_mem).resolve().parent.parent)
    return str(root)


def resolve_project() -> str:
    """Auto-detect project from git root (matches bin/wt-memory resolve_project)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return "_global"
        toplevel = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return "_global"

    # Worktree detection: git-common-dir points to main repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
        common_dir = result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        common_dir = ""

    if common_dir and common_dir != ".git":
        # Worktree: resolve to main repo name
        abs_common = os.path.normpath(os.path.join(toplevel, common_dir))
        return os.path.basename(os.path.dirname(abs_common))

    return os.path.basename(toplevel)
