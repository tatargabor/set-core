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

from .anomaly import (
    AnomalyContext,
    AnomalyTrigger,
    KNOWN_EVENT_TYPES,
    scan_for_anomalies,
)
from .canary import CanaryRunner, build_canary_diff
from .ephemeral import spawn_ephemeral_claude
from .inbox import InboxMessage, classify_message, read_new_messages
from .state import SupervisorStatus, read_status, write_status
from .triggers import TriggerExecutor

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

        # Phase 2: anomaly + canary infrastructure. Both readers/writers
        # of the orchestration state and events files; we resolve the
        # paths once via SetRuntime and reuse them every poll.
        self._state_path, self._events_path, self._log_path = self._resolve_runtime_paths()
        self._known_event_types: set[str] = set(self.status.known_event_types or [])
        self._error_baseline: dict = dict(self.status.error_baseline or {})
        self._trigger_executor = TriggerExecutor(
            status=self.status,
            project_path=self.project_path,
            events_path=self._events_path or (self.project_path / "orchestration-events.jsonl"),
            spec=config.spec,
            emit_event=self._emit_event,
        )
        self._canary_runner = CanaryRunner(
            status=self.status,
            project_path=self.project_path,
            spec=config.spec,
            emit_event=self._emit_event,
        )
        # Seed last_canary_at on first start so the very first canary fires
        # 15 minutes AFTER daemon start, not immediately. The orchestrator
        # has barely had time to do anything 15s after launch — there's
        # nothing useful for a canary to evaluate yet, and skipping the
        # immediate fire avoids burning a Claude call on every supervisor
        # restart (and unblocks tests that don't mock the canary).
        if not self.status.last_canary_at:
            self.status.last_canary_at = _now_iso()
        self._last_canary_window_iso = self.status.last_canary_at

        write_status(self.project_path, self.status)

    def _is_state_terminal(self) -> bool:
        """Check whether orchestration-state.json reports a terminal status.

        Used by the monitor loop to distinguish a clean orchestrator exit
        (terminal status) from a crash (status still running). Terminal
        statuses are sourced from `anomaly.TERMINAL_STATUSES` so the two
        modules cannot drift apart.
        """
        if not self._state_path or not self._state_path.is_file():
            return False
        try:
            data = json.loads(self._state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return False
        from .anomaly import TERMINAL_STATUSES
        return (data.get("status") or "").lower() in TERMINAL_STATUSES

    def _resolve_runtime_paths(self) -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """Locate the orchestration state, events, and log files.

        The orchestrator has a hybrid path layout that the supervisor must
        navigate carefully to avoid reading from the wrong (sparse) source:

          STATE:
            - canonical:  `<project>/orchestration-state.json`
              (set-orchestrate CLI's `--state` arg points here on every
              real run; manager API doesn't override it)
            - SetRuntime path is reserved but never populated in practice

          EVENTS:
            - canonical:  `<project>/orchestration-events.jsonl`
              (where DISPATCH, STATE_CHANGE, GATE_*, VERIFY_GATE, MERGE_*,
              WATCHDOG_*, MONITOR_*, CHANGE_DONE, CLASSIFIER_CALL, plus
              SUPERVISOR_* events from the daemon itself all land —
              ~570 events on a typical nano run)
            - SetRuntime path  contains only digest-phase LLM_CALLs from
              the event_bus singleton's first init (~3 events on nano).
              Reading the SetRuntime path silently misses 99% of events.

          LOG:
            - canonical:  SetRuntime's `<runtime>/logs/orchestration.log`
              (the orchestrator's stdlib logger writes here)

        Resolution policy: try the CANONICAL path first for each artifact,
        fall back to SetRuntime second. The canonical file may not exist
        yet at daemon startup — `_build_anomaly_context` calls this
        function lazily each poll until all three paths resolve.

        This is the same hybrid-path bug as state, but for events. State
        was easy because the SetRuntime state file NEVER exists, so the
        original "SetRuntime first, project fallback" logic happened to
        work via fall-through. For events the SetRuntime file DOES exist
        (with sparse content), so the fall-through silently picked the
        wrong file. Hence: explicit canonical-first ordering everywhere.
        """
        candidates_state: list[Path] = []
        candidates_events: list[Path] = []
        candidates_log: list[Path] = []

        # CANONICAL paths first (project-relative for state + events)
        candidates_state.append(self.project_path / "orchestration-state.json")
        candidates_events.append(self.project_path / "orchestration-events.jsonl")

        # SetRuntime as the secondary source (canonical for log)
        try:
            from ..paths import SetRuntime
            rt = SetRuntime(str(self.project_path))
            candidates_log.append(Path(rt.orchestration_log))
            candidates_state.append(Path(rt.state_file))
            candidates_events.append(Path(rt.events_file))
        except Exception as exc:
            logger.warning("[supervisor] SetRuntime path resolution failed: %s", exc)

        # Pick first existing file for state + log
        state_path: Optional[Path] = next(
            (p for p in candidates_state if p.is_file()), None,
        )
        log_path: Optional[Path] = next(
            (p for p in candidates_log if p.is_file()), None,
        )

        # Events: prefer first existing file. If none exist, fall back to
        # the first candidate whose PARENT directory exists — so a poll
        # before the orchestrator's first emit still has a valid path
        # to tail (it will be empty, which is fine).
        events_path: Optional[Path] = None
        for p in candidates_events:
            if p.is_file():
                events_path = p
                break
        if events_path is None:
            for p in candidates_events:
                if p.parent.is_dir():
                    events_path = p
                    break

        logger.info(
            "[supervisor] Resolved paths: state=%s events=%s log=%s",
            state_path, events_path, log_path,
        )
        return state_path, events_path, log_path

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

            # 1. Process alive check. Four cases by (poll_result, state.status):
            #    (alive)            → continue normally
            #    (exit 0, *)        → clean exit, treat as orchestrator_done.
            #                         If state is terminal, run a final
            #                         anomaly scan first so the terminal_state
            #                         trigger fires and the final-report
            #                         Claude is spawned via the normal pipe.
            #    (exit != 0, term)  → orchestrator died with non-zero status
            #                         but state already terminal → also treat
            #                         as orchestrator_exit_N, no restart.
            #    (exit != 0, run)   → real crash, restart via the rapid-crash
            #                         counter.
            #
            # We call Popen.poll() FIRST so the zombie gets reaped — if we
            # only checked _is_alive() (kill -0), an unreaped zombie would
            # still report as alive forever and the daemon would never
            # detect the orchestrator's exit. _is_alive() is the secondary
            # source of truth (for the case when self._orch_proc is None).
            poll_result = (
                self._orch_proc.poll() if self._orch_proc is not None else None
            )
            orch_alive = (
                self._orch_proc is not None
                and poll_result is None
                and _is_alive(self._orch_proc.pid)
            )
            if not orch_alive and not self._stop_requested:
                exit_code = poll_result if poll_result is not None else 0
                state_terminal = self._is_state_terminal()

                if state_terminal:
                    # Orchestration finished naturally → fire terminal_state
                    # trigger so the final-report Claude is spawned through
                    # the normal anomaly pipeline.
                    logger.info(
                        "[supervisor] Orchestrator done + state terminal — "
                        "running final anomaly scan (exit=%d)",
                        exit_code,
                    )
                    try:
                        self._scan_and_dispatch_anomalies()
                    except Exception:
                        logger.exception("[supervisor] Final anomaly scan crashed")
                    self._stop_reason = (
                        "orchestrator_done" if exit_code == 0
                        else f"orchestrator_exit_{exit_code}"
                    )
                    self._stop_requested = True
                    break

                if exit_code == 0:
                    # Clean exit but state.json says not-terminal — likely
                    # an external kill or a non-orchestrator process. No
                    # final report needed. Don't restart, just shut down.
                    logger.info(
                        "[supervisor] Orchestrator exited code 0 but state "
                        "not terminal — shutting down without final scan",
                    )
                    self._stop_reason = "orchestrator_done"
                    self._stop_requested = True
                    break

                # Crash path: non-zero exit AND state not terminal → restart
                if not self._restart_orchestrator():
                    break
                continue

            # 2. Inbox check
            self._check_inbox()
            if self._stop_requested:
                break

            # 4. Phase 2: anomaly signal detection + ephemeral Claude dispatch.
            try:
                self._scan_and_dispatch_anomalies()
            except Exception:
                logger.exception("[supervisor] Anomaly scan crashed — continuing")

            # 5. Phase 2: periodic canary check (cheap is_due() poll, expensive
            #    LLM call only when due).
            try:
                if self._canary_runner.is_due():
                    self._run_canary()
            except Exception:
                logger.exception("[supervisor] Canary run crashed — continuing")

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

    # ── Phase 2: anomaly + canary ────────────────────────

    def _scan_and_dispatch_anomalies(self) -> None:
        """Build an AnomalyContext, run all detectors, dispatch via TriggerExecutor."""
        ctx = self._build_anomaly_context()
        triggers = scan_for_anomalies(ctx)

        # Persist any state mutated by the detectors back into status
        self.status.known_event_types = sorted(self._known_event_types)
        self.status.error_baseline = dict(self._error_baseline)
        self.status.last_state_mtime = ctx.state_mtime
        self.status.last_state_change_at = ctx.last_state_change_at
        if ctx.log_size > self.status.last_log_size:
            self.status.last_log_growth_at = ctx.now
        self.status.last_log_size = ctx.log_size

        if not triggers:
            return

        logger.info(
            "[supervisor] Anomaly scan: %d trigger(s) firing — %s",
            len(triggers), ", ".join(f"{t.type}({t.change or '-'})" for t in triggers),
        )
        outcomes = self._trigger_executor.execute(triggers)

        # If a terminal_state trigger actually dispatched, request shutdown.
        for o in outcomes:
            if o.trigger.type == "terminal_state" and o.result is not None:
                logger.info("[supervisor] terminal_state trigger fired — requesting shutdown")
                self._stop_requested = True
                self._stop_reason = "terminal_state"
                break

    def _build_anomaly_context(self) -> AnomalyContext:
        """Snapshot all the inputs detectors need this poll cycle."""
        # Lazy path re-resolution. Three artifacts (state, events, log)
        # may not exist at daemon-start time and have to be re-checked
        # each poll until they appear. The events path is doubly tricky:
        #   - the canonical project-relative file may not exist yet
        #     when the daemon starts, but the SetRuntime fallback DOES
        #     exist (with sparse digest-phase events)
        #   - if we picked the SetRuntime file early, we MUST upgrade to
        #     the canonical file as soon as it appears, otherwise the
        #     supervisor reads only ~3 events for the entire run
        #
        # We re-resolve on every poll while ANY of the three paths is
        # either None or pointing at a non-canonical fallback. Cheap —
        # at most six stat calls per poll, all O(1).
        canonical_state = self.project_path / "orchestration-state.json"
        canonical_events = self.project_path / "orchestration-events.jsonl"
        needs_state = self._state_path is None or self._state_path != canonical_state
        needs_events = (
            self._events_path is None
            or (self._events_path != canonical_events and canonical_events.is_file())
        )
        needs_log = self._log_path is None
        if needs_state or needs_events or needs_log:
            sp, ep, lp = self._resolve_runtime_paths()
            if needs_state and sp is not None and sp != self._state_path:
                logger.info("[supervisor] state path resolved (lazy): %s", sp)
                self._state_path = sp
            if needs_log and lp is not None:
                logger.info("[supervisor] log path resolved (lazy): %s", lp)
                self._log_path = lp
            if needs_events and ep is not None and ep != self._events_path:
                old_events = self._events_path
                logger.info(
                    "[supervisor] events path resolved (lazy): %s (was %s)",
                    ep, old_events,
                )
                self._events_path = ep
                # The trigger executor captured the old (None or stale)
                # events path at __init__; update it so prior_attempts
                # summaries find the right file.
                self._trigger_executor.events_path = ep
                # Reset the byte-offset cursor — it was an offset into a
                # different file and would skip events on the new one.
                # Re-scan from the beginning of the canonical file.
                if old_events != ep:
                    self.status.events_cursor = 0

        # State
        state_dict: Optional[dict] = None
        state_mtime: float = 0.0
        if self._state_path and self._state_path.is_file():
            try:
                state_dict = json.loads(self._state_path.read_text())
                state_mtime = self._state_path.stat().st_mtime
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("[supervisor] Could not read state file: %s", exc)

        last_state_change_at = self.status.last_state_change_at
        if state_mtime > self.status.last_state_mtime:
            last_state_change_at = time.time()
        elif last_state_change_at <= 0 and state_mtime > 0:
            # First poll observing this file — seed the timestamp so we don't
            # immediately fire state_stall against an unknown baseline.
            last_state_change_at = time.time()

        # Events: read since last cursor
        new_events: list[dict] = []
        if self._events_path and self._events_path.is_file():
            new_events, new_cursor = self._read_new_events(
                self._events_path, self.status.events_cursor,
            )
            self.status.events_cursor = new_cursor

        # Log size
        log_size = 0
        if self._log_path and self._log_path.is_file():
            try:
                log_size = self._log_path.stat().st_size
            except OSError:
                log_size = 0

        orchestrator_pid = self._orch_proc.pid if self._orch_proc else 0
        orchestrator_alive = (
            self._orch_proc is not None and _is_alive(self._orch_proc.pid)
        )

        return AnomalyContext(
            project_path=self.project_path,
            state_path=self._state_path,
            events_path=self._events_path,
            log_path=self._log_path,
            state=state_dict,
            new_events=new_events,
            orchestrator_pid=orchestrator_pid,
            orchestrator_alive=orchestrator_alive,
            now=time.time(),
            state_mtime=state_mtime,
            last_state_mtime=self.status.last_state_mtime,
            last_state_change_at=last_state_change_at,
            log_size=log_size,
            last_log_size=self.status.last_log_size,
            last_log_growth_at=self.status.last_log_growth_at,
            error_baseline=self._error_baseline,
            known_event_types=self._known_event_types,
        )

    def _read_new_events(self, path: Path, cursor: int) -> tuple[list[dict], int]:
        """Read events.jsonl from `cursor` to EOF. Returns (events, new_cursor).

        Bounded read: at most ~5 MB per call to keep poll cycles cheap on
        runaway logs.
        """
        out: list[dict] = []
        try:
            size = path.stat().st_size
        except OSError:
            return [], cursor
        if size <= cursor:
            return [], cursor
        max_read = 5 * 1024 * 1024
        if size - cursor > max_read:
            cursor = size - max_read  # skip ahead, drop old events
        try:
            with open(path, "r") as f:
                f.seek(cursor)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                new_cursor = f.tell()
        except OSError as exc:
            logger.warning("[supervisor] Could not read events file: %s", exc)
            return [], cursor
        return out, new_cursor

    def _run_canary(self) -> None:
        """Build a CanaryDiff and ask the canary runner to spawn its Claude."""
        # Reuse the most recent anomaly context's inputs if possible —
        # otherwise rebuild a minimal one for state snapshot
        state_dict: Optional[dict] = None
        if self._state_path and self._state_path.is_file():
            try:
                state_dict = json.loads(self._state_path.read_text())
            except (OSError, json.JSONDecodeError):
                state_dict = None

        new_events: list[dict] = []
        if self._events_path and self._events_path.is_file():
            new_events, _ = self._read_new_events(
                self._events_path, self.status.events_cursor,
            )

        log_warns = 0
        log_errors = 0
        if self._log_path and self._log_path.is_file():
            from .anomaly import _count_log_severity
            log_warns, log_errors = _count_log_severity(
                self._log_path, self.status.last_log_size, self._log_path.stat().st_size,
            )

        window_end = _now_iso()
        diff = build_canary_diff(
            state=state_dict,
            new_events=new_events,
            poll_cycle=self.status.poll_cycle,
            window_start_iso=self._last_canary_window_iso,
            window_end_iso=window_end,
            log_warns=log_warns,
            log_errors=log_errors,
        )
        logger.info(
            "[supervisor] Running canary: merged=%d running=%d failed=%d",
            len(diff.merged_changes), len(diff.running_changes),
            len(diff.failed_changes),
        )
        run = self._canary_runner.run(diff)
        self._last_canary_window_iso = window_end

        # Stop on STOP verdict
        if run.verdict == "stop":
            logger.error(
                "[supervisor] Canary returned STOP — halting orchestrator for user review"
            )
            self._stop_requested = True
            self._stop_reason = "canary_stop"

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
