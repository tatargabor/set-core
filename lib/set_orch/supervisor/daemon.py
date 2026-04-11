"""SupervisorDaemon — the main set-supervisor daemon (Phase 1 MVP).

Long-running Python process that:
1. Starts the orchestrator as a subprocess
2. Monitors the orchestrator PID (cheap poll every 15s)
3. Restarts the orchestrator on crash (up to 3 rapid crashes, then halts)
4. Handles the user inbox (stop/status messages) every poll
5. Emits observability events (SUPERVISOR_START/STOP/RESTART) to the
   project's orchestration-events.jsonl file
6. Persists its state in .set/supervisor/status.json so a restarted
   daemon picks up where the old one left off
7. Responds to SIGTERM by gracefully stopping the orchestrator and
   writing a final status.json

Phase 2 (separate change) will add anomaly signal detection + ephemeral
Claude triggers + periodic canary checks. The hooks are defined in this
file but NOT called on the routine path.

Entry point: `bin/set-supervisor --project <path> --spec <path>`
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ephemeral import spawn_ephemeral_claude
from .inbox import InboxMessage, classify_message, read_new_messages
from .state import SupervisorStatus, read_status, write_status

logger = logging.getLogger(__name__)


POLL_INTERVAL_SECONDS = 15
RAPID_CRASH_WINDOW_SECONDS = 300  # 5 min
RAPID_CRASH_LIMIT = 3
SIGTERM_GRACE_SECONDS = 30


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _kill_graceful(pid: int, timeout: Optional[int] = None) -> None:
    """SIGTERM with timeout, SIGKILL on fallthrough.

    `timeout` defaults to the module-level SIGTERM_GRACE_SECONDS looked
    up at call time (so tests can monkeypatch the module attribute to
    shorten the wait in unit tests).
    """
    if timeout is None:
        timeout = SIGTERM_GRACE_SECONDS
    if not _is_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _is_alive(pid):
            return
        time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@dataclass
class SupervisorConfig:
    """Configuration for a single daemon instance."""
    project_path: str
    spec: str
    orch_binary: str = "set-orchestrate"
    orch_extra_args: list = field(default_factory=list)
    poll_interval: int = POLL_INTERVAL_SECONDS
    rapid_crash_limit: int = RAPID_CRASH_LIMIT
    rapid_crash_window: int = RAPID_CRASH_WINDOW_SECONDS


class SupervisorDaemon:
    """Phase 1 MVP supervisor daemon.

    Usage::

        cfg = SupervisorConfig(project_path="/path/to/project",
                                spec="docs/spec.md")
        daemon = SupervisorDaemon(cfg)
        daemon.run()
    """

    def __init__(self, config: SupervisorConfig):
        self.config = config
        self.project_path = Path(config.project_path)
        self.status = read_status(self.project_path)
        # Reset volatile fields on fresh daemon start — but keep counters
        self.status.daemon_pid = os.getpid()
        self.status.daemon_started_at = _now_iso()
        self.status.spec = config.spec
        self.status.status = "starting"
        self.status.stop_reason = ""
        self._orch_proc: Optional[subprocess.Popen] = None
        self._stop_requested = False
        self._stop_reason = ""
        self._last_event_ts = time.time()
        write_status(self.project_path, self.status)

    # ── Lifecycle ────────────────────────────────────────

    def run(self) -> int:
        """Main entry point — starts the orchestrator and enters the poll loop.

        Returns the daemon exit code: 0 for clean shutdown, 1 for crash.
        """
        self._install_signal_handlers()
        logger.info(
            "[supervisor] START project=%s spec=%s daemon_pid=%d",
            self.project_path.name, self.config.spec, os.getpid(),
        )
        self._emit_event("SUPERVISOR_START", {
            "daemon_pid": os.getpid(),
            "project": self.project_path.name,
            "spec": self.config.spec,
        })

        try:
            self._spawn_orchestrator()
        except Exception as exc:
            logger.exception("[supervisor] Could not start orchestrator: %s", exc)
            self._shutdown("orchestrator_spawn_failed")
            return 1

        try:
            exit_code = self._monitor_loop()
        except KeyboardInterrupt:
            logger.info("[supervisor] KeyboardInterrupt — shutting down")
            exit_code = 0
        except Exception as exc:
            logger.exception("[supervisor] Monitor loop crashed: %s", exc)
            exit_code = 1
        finally:
            self._shutdown(self._stop_reason or "monitor_loop_exit")

        return exit_code

    # ── Signal handling ──────────────────────────────────

    def _install_signal_handlers(self) -> None:
        def handle_stop(signum, frame):
            name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
            logger.info("[supervisor] Received %s — requesting graceful stop", name)
            self._stop_requested = True
            self._stop_reason = f"signal_{name}"

        signal.signal(signal.SIGTERM, handle_stop)
        signal.signal(signal.SIGINT, handle_stop)

    # ── Orchestrator lifecycle ───────────────────────────

    def _spawn_orchestrator(self) -> None:
        """Spawn `set-orchestrate` as a subprocess."""
        cmd = [self.config.orch_binary, "start", "--spec", self.config.spec]
        cmd.extend(self.config.orch_extra_args)

        env = os.environ.copy()
        set_core_bin = Path(__file__).resolve().parent.parent.parent.parent / "bin"
        if set_core_bin.is_dir():
            env["PATH"] = f"{set_core_bin}:{env.get('PATH', '')}"

        # Log orchestrator stdout/stderr to files under runtime
        log_dir = self.project_path / ".set" / "supervisor" / "orch-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        stdout_path = log_dir / f"orch-{ts}.stdout.log"
        stderr_path = log_dir / f"orch-{ts}.stderr.log"

        stdout_f = open(stdout_path, "wb")
        stderr_f = open(stderr_path, "wb")

        logger.info("[supervisor] Spawning orchestrator: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_path),
            stdout=stdout_f,
            stderr=stderr_f,
            env=env,
            start_new_session=True,
        )
        self._orch_proc = proc
        self.status.orchestrator_pid = proc.pid
        self.status.orchestrator_started_at = _now_iso()
        self.status.status = "running"
        write_status(self.project_path, self.status)
        logger.info("[supervisor] Orchestrator started pid=%d", proc.pid)

    def _restart_orchestrator(self) -> bool:
        """Restart orchestrator after a crash. Returns True if restarted, False if rapid-crash exhausted."""
        now = time.time()
        # Reset window if expired
        if now - self.status.rapid_crashes_window_start > self.config.rapid_crash_window:
            self.status.rapid_crashes = 0
            self.status.rapid_crashes_window_start = now
        self.status.rapid_crashes += 1
        logger.warning(
            "[supervisor] Orchestrator crashed (rapid_crashes=%d/%d in window)",
            self.status.rapid_crashes, self.config.rapid_crash_limit,
        )
        if self.status.rapid_crashes >= self.config.rapid_crash_limit:
            logger.error(
                "[supervisor] Rapid crash limit exceeded — halting daemon"
            )
            self._stop_reason = "rapid_crash_limit_exceeded"
            self._stop_requested = True
            return False

        self._emit_event("SUPERVISOR_RESTART", {
            "rapid_crashes": self.status.rapid_crashes,
            "reason": "orchestrator_crash",
        })
        try:
            self._spawn_orchestrator()
            return True
        except Exception as exc:
            logger.exception("[supervisor] Failed to restart orchestrator: %s", exc)
            self._stop_reason = "restart_failed"
            self._stop_requested = True
            return False

    def _shutdown(self, reason: str) -> None:
        """Graceful shutdown — stops orchestrator, writes terminal status."""
        logger.info("[supervisor] Shutdown initiated: reason=%s", reason)
        self.status.status = "stopping"
        self.status.stop_reason = reason
        write_status(self.project_path, self.status)

        if self._orch_proc and _is_alive(self._orch_proc.pid):
            _kill_graceful(self._orch_proc.pid)

        self.status.status = "stopped"
        write_status(self.project_path, self.status)
        self._emit_event("SUPERVISOR_STOP", {
            "reason": reason,
            "poll_cycle": self.status.poll_cycle,
            "rapid_crashes": self.status.rapid_crashes,
        })
        logger.info("[supervisor] Shutdown complete")

    # ── Monitor loop ──────────────────────────────────────

    def _monitor_loop(self) -> int:
        """Main poll loop. Runs until _stop_requested or rapid-crash-exhausted."""
        while not self._stop_requested:
            self.status.poll_cycle += 1

            # 1. Process alive check
            orch_alive = self._orch_proc is not None and _is_alive(self._orch_proc.pid)
            if not orch_alive and not self._stop_requested:
                if not self._restart_orchestrator():
                    break
                continue

            # 2. Inbox check
            self._check_inbox()
            if self._stop_requested:
                break

            # 3. Terminal state check (if orchestrator finished on its own)
            if self._orch_proc and self._orch_proc.poll() is not None:
                exit_code = self._orch_proc.returncode
                logger.info(
                    "[supervisor] Orchestrator exited cleanly with code=%d", exit_code,
                )
                if exit_code == 0:
                    self._stop_reason = "orchestrator_done"
                else:
                    self._stop_reason = f"orchestrator_exit_{exit_code}"
                self._stop_requested = True
                break

            # 4. (Phase 2 hook) Anomaly signal detection — currently no-op
            # from .anomaly import scan_for_anomalies
            # triggers = scan_for_anomalies(self.project_path, self.status)
            # for t in triggers: self._fire_trigger(t)

            # 5. (Phase 2 hook) Periodic canary check — currently no-op
            # if self._canary_due():
            #     self._run_canary()

            # 6. Persist status (cheap — tmpfile + rename)
            self.status.last_event_at = _now_iso()
            write_status(self.project_path, self.status)

            # 7. Sleep with early-wake on signal
            for _ in range(self.config.poll_interval):
                if self._stop_requested:
                    break
                time.sleep(1)

        return 0

    # ── Inbox handling ────────────────────────────────────

    def _check_inbox(self) -> None:
        messages = read_new_messages(self.project_path)
        for msg in messages:
            action = classify_message(msg)
            logger.info(
                "[supervisor] Inbox message: from=%s action=%s content=%r",
                msg.sender, action, msg.content[:100],
            )
            if action == "stop":
                self._stop_requested = True
                self._stop_reason = f"inbox_stop:{msg.sender}"
                self._emit_event("SUPERVISOR_INBOX", {
                    "action": "stop", "from": msg.sender,
                })
                return
            if action == "status":
                self._respond_status(msg)
                continue
            # Unknown — log and continue. Phase 2: pass to ephemeral Claude
            # for interpretation if the daemon doesn't recognise the intent.
            self._emit_event("SUPERVISOR_INBOX", {
                "action": "other", "from": msg.sender, "content": msg.content[:200],
            })

    def _respond_status(self, msg: InboxMessage) -> None:
        """Write current status to an inbox response file."""
        response_path = self.project_path / ".set" / "sentinel" / "inbox-response.json"
        try:
            response_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "to": msg.sender,
                "timestamp": _now_iso(),
                "daemon_pid": self.status.daemon_pid,
                "orchestrator_pid": self.status.orchestrator_pid,
                "poll_cycle": self.status.poll_cycle,
                "rapid_crashes": self.status.rapid_crashes,
                "status": self.status.status,
            }
            response_path.write_text(json.dumps(payload, indent=2))
        except OSError as exc:
            logger.warning("[supervisor] Could not write inbox response: %s", exc)

    # ── Event emission ────────────────────────────────────

    def _emit_event(self, event_type: str, data: dict) -> None:
        """Append an event to the project's orchestration-events.jsonl."""
        event = {
            "ts": _now_iso(),
            "type": event_type,
            "data": data,
        }
        path = self.project_path / "orchestration-events.jsonl"
        try:
            with open(path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError as exc:
            logger.warning("[supervisor] Could not emit event %s: %s", event_type, exc)
