"""Project Supervisor — manages sentinel + orchestrator lifecycle per project."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..issues.models import now_iso

logger = logging.getLogger(__name__)

SENTINEL_PROMPT_FALLBACK = (
    "You are the sentinel monitoring project '{project}' at {path}. "
    "Run the sentinel polling loop: monitor orchestration state, detect errors, "
    "write findings to .set/sentinel/findings.json. "
    "Poll every 15 seconds. Never stop on your own."
)

SENTINEL_SKILL_PATH = ".claude/commands/set/sentinel.md"

MAX_CRASH_RESTARTS = 5


@dataclass
class ProjectConfig:
    name: str
    path: Path
    mode: str = "e2e"  # e2e | production | development
    sentinel_enabled: bool = True
    auto_restart_sentinel: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "mode": self.mode,
            "sentinel_enabled": self.sentinel_enabled,
            "auto_restart_sentinel": self.auto_restart_sentinel,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectConfig:
        d = dict(data)
        d["path"] = Path(d["path"])
        known = {f.name for f in cls.__dataclass_fields__.values()}
        d = {k: v for k, v in d.items() if k in known}
        return cls(**d)


def _is_alive(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    # Check for zombie (defunct) — os.kill succeeds but process is dead
    try:
        stat = Path(f"/proc/{pid}/status").read_text()
        if "zombie" in stat.lower():
            # Reap the zombie
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            return False
    except (FileNotFoundError, PermissionError):
        pass
    return True


def _kill_gracefully(pid: int, timeout: int = 5):
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


class ProjectSupervisor:
    """Manages sentinel + orchestrator lifecycle for one project."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.sentinel_pid: Optional[int] = None
        self.sentinel_started_at: Optional[str] = None
        self.sentinel_spec: Optional[str] = None
        # Restore last-used spec from disk
        try:
            marker = Path(config.path) / "set" / "orchestration" / ".sentinel-spec"
            if marker.is_file():
                self.sentinel_spec = marker.read_text().strip() or None
        except OSError:
            pass
        self.sentinel_crash_count: int = 0
        self.orchestrator_pid: Optional[int] = None
        self.orchestrator_started_at: Optional[str] = None
        self._sentinel_proc: Optional[subprocess.Popen] = None
        self._orch_proc: Optional[subprocess.Popen] = None
        self._manually_stopped: bool = False

        # Reattach to a still-running sentinel after a set-web restart. The
        # supervisor's own status.json records the live daemon PID; if the
        # process is alive we adopt it as-is so the manager keeps observing
        # instead of treating it as stopped (and refusing to track it). The
        # sentinel itself runs in its own session so it survives set-web
        # restarts cleanly.
        try:
            status_json = (
                Path(config.path) / ".set" / "supervisor" / "status.json"
            )
            if status_json.is_file():
                import json as _json
                persisted = _json.loads(status_json.read_text())
                persisted_pid = persisted.get("daemon_pid")
                if (
                    isinstance(persisted_pid, int)
                    and persisted_pid > 0
                    and _is_alive(persisted_pid)
                    and persisted.get("status") != "stopped"
                ):
                    self.sentinel_pid = persisted_pid
                    self.sentinel_started_at = persisted.get("daemon_started_at")
                    self.sentinel_spec = persisted.get("spec") or self.sentinel_spec
                    self.orchestrator_pid = persisted.get("orchestrator_pid")
                    self.orchestrator_started_at = persisted.get(
                        "orchestrator_started_at"
                    )
                    logger.info(
                        f"[{config.name}] Reattached to live sentinel "
                        f"PID={persisted_pid}"
                    )
        except (OSError, ValueError, TypeError):
            pass

    def _load_sentinel_prompt(self, spec: Optional[str] = None) -> str:
        """Load sentinel skill file as prompt, with fallback to hardcoded prompt.

        Always injects --managed flag so the sentinel skill's launch guard
        knows it was started by the manager (not accidentally by an agent).
        Without --managed, the skill refuses to run and redirects to /set:start.
        """
        skill_file = self.config.path / SENTINEL_SKILL_PATH
        if skill_file.is_file():
            prompt = skill_file.read_text(encoding="utf-8")
            logger.info(f"[{self.config.name}] Loaded sentinel skill from {skill_file}")
        else:
            logger.warning(
                f"[{self.config.name}] Sentinel skill not found at {skill_file}, "
                "using fallback prompt"
            )
            prompt = SENTINEL_PROMPT_FALLBACK.format(
                project=self.config.name,
                path=self.config.path,
            )

        # Always inject --managed flag so the skill knows it was launched by the manager
        prompt += "\n\nArguments: --managed"
        if spec:
            prompt += f" --spec {spec}"

        return prompt

    def _supervisor_mode(self) -> str:
        """Read the supervisor_mode directive from the project's state.

        Falls back to "python" (default) if the directive is missing or
        the state file is unreadable. Valid values: python | claude | off.
        """
        state_file = self.config.path / "orchestration-state.json"
        if not state_file.is_file():
            return "python"
        try:
            import json as _json
            data = _json.loads(state_file.read_text())
            mode = (data.get("directives") or {}).get("supervisor_mode", "python")
            return str(mode).lower()
        except Exception:
            return "python"

    def start_sentinel(self, spec: Optional[str] = None) -> int:
        """Spawn the supervisor for this project.

        Dispatches based on the project's `supervisor_mode` directive:
        - "python" (default): spawn `set-supervisor` Python daemon
        - "claude": spawn the legacy Claude-driven sentinel skill
        - "off": start the orchestrator directly with no supervision
        """
        mode = self._supervisor_mode()
        if mode == "python":
            return self._start_python_supervisor(spec=spec)
        if mode == "off":
            return self._start_orchestrator_unsupervised(spec=spec)
        # mode == "claude" → legacy path (or any unknown value, for safety)
        return self._start_claude_sentinel(spec=spec)

    def _start_python_supervisor(self, spec: Optional[str] = None) -> int:
        """Spawn the set-supervisor Python daemon."""
        if not spec:
            raise RuntimeError("supervisor_mode=python requires a spec path")

        try:
            from ..paths import SetRuntime
            log_dir = Path(SetRuntime(str(self.config.path)).sentinel_dir)
        except Exception:
            log_dir = self.config.path / ".set" / "sentinel"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_file = open(log_dir / "stdout.log", "w")
        stderr_file = open(log_dir / "stderr.log", "w")

        set_core_bin = Path(__file__).resolve().parent.parent.parent.parent / "bin"
        cmd = [
            str(set_core_bin / "set-supervisor"),
            "--project", str(self.config.path),
            "--spec", spec,
        ]

        env = os.environ.copy()
        if set_core_bin.is_dir():
            env["PATH"] = f"{set_core_bin}:{env.get('PATH', '')}"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.path),
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
                env=env,
            )
            self._sentinel_proc = proc
            self.sentinel_pid = proc.pid
            self.sentinel_started_at = now_iso()
            self.sentinel_spec = spec
            try:
                marker = Path(self.config.path) / "set" / "orchestration" / ".sentinel-spec"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(spec or "")
            except OSError:
                pass
            self.sentinel_crash_count = 0
            self._manually_stopped = False
            logger.info(f"[{self.config.name}] Python supervisor started, PID={proc.pid}")
            return proc.pid
        except FileNotFoundError as exc:
            logger.error(f"[{self.config.name}] set-supervisor not found: {exc}")
            raise

    def _start_orchestrator_unsupervised(self, spec: Optional[str] = None) -> int:
        """Start set-orchestrate directly with no supervisor wrapper."""
        if not spec:
            raise RuntimeError("supervisor_mode=off requires a spec path")
        cmd = ["set-orchestrate", "start", "--spec", spec]
        try:
            from ..paths import SetRuntime
            log_dir = Path(SetRuntime(str(self.config.path)).sentinel_dir)
        except Exception:
            log_dir = self.config.path / ".set" / "sentinel"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_file = open(log_dir / "stdout.log", "w")
        stderr_file = open(log_dir / "stderr.log", "w")
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.config.path),
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )
        self._orch_proc = proc
        self.orchestrator_pid = proc.pid
        self.orchestrator_started_at = now_iso()
        self.sentinel_pid = proc.pid  # Manager API tracks this as the "supervisor" pid
        self.sentinel_started_at = self.orchestrator_started_at
        self.sentinel_spec = spec
        logger.info(f"[{self.config.name}] Orchestrator started unsupervised, PID={proc.pid}")
        return proc.pid

    def _start_claude_sentinel(self, spec: Optional[str] = None) -> int:
        """Legacy path — spawn the Claude sentinel skill via `claude -p`."""
        prompt = self._load_sentinel_prompt(spec=spec)
        # Log stdout and stderr to files for debugging
        try:
            from ..paths import SetRuntime
            sentinel_log = Path(SetRuntime(str(self.config.path)).sentinel_dir)
        except Exception:
            sentinel_log = self.config.path / ".set" / "sentinel"
        sentinel_log.mkdir(parents=True, exist_ok=True)
        stdout_file = open(sentinel_log / "stdout.log", "w")
        stderr_file = open(sentinel_log / "stderr.log", "w")

        cmd = ["claude", "-p", "--model", "sonnet", "--max-turns", "500",
               "--dangerously-skip-permissions",
               "--verbose", "--output-format", "stream-json"]

        # Ensure set-core bin/ is on PATH so sentinel can call set-sentinel-finding etc.
        env = os.environ.copy()
        set_core_bin = Path(__file__).resolve().parent.parent.parent.parent / "bin"
        if set_core_bin.is_dir():
            env["PATH"] = f"{set_core_bin}:{env.get('PATH', '')}"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.path),
                stdin=subprocess.PIPE,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
                env=env,
            )
            # Send prompt via stdin — avoids command-line length limits
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
            self._sentinel_proc = proc
            self.sentinel_pid = proc.pid
            self.sentinel_started_at = now_iso()
            self.sentinel_spec = spec
            # Persist spec path for future restarts
            try:
                marker = Path(self.config.path) / "set" / "orchestration" / ".sentinel-spec"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(spec or "")
            except OSError:
                pass
            self.sentinel_crash_count = 0
            self._manually_stopped = False
            logger.info(f"[{self.config.name}] Sentinel started, PID={proc.pid}")
            return proc.pid
        except FileNotFoundError:
            logger.error(f"[{self.config.name}] claude CLI not found")
            raise

    def stop_sentinel(self):
        """Gracefully stop sentinel agent and its child processes (orchestrator etc.)."""
        self._manually_stopped = True
        if self.sentinel_pid and _is_alive(self.sentinel_pid):
            _kill_gracefully(self.sentinel_pid)
            logger.info(f"[{self.config.name}] Sentinel stopped (PID={self.sentinel_pid})")
        # Also stop orchestrator if it was spawned by the sentinel
        self._kill_orphan_orchestrator()
        self.sentinel_pid = None
        self.sentinel_started_at = None
        self.sentinel_spec = None
        self._sentinel_proc = None

    def _kill_orphan_orchestrator(self):
        """Find and kill orchestrator processes for this project that may outlive the sentinel."""
        import subprocess as _sp
        state_path = str(self.config.path)
        for pattern in [f"engine monitor.*{state_path}", f"set-orchestrate.*{state_path}"]:
            try:
                result = _sp.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.strip().splitlines():
                    if not line.strip():
                        continue
                    pid = int(line.strip())
                    if pid and _is_alive(pid):
                        _kill_gracefully(pid)
                        logger.info(f"[{self.config.name}] Killed orphan orchestrator PID={pid}")
            except (ValueError, OSError, _sp.TimeoutExpired):
                pass

    def start_orchestration(self, plan_file: Optional[str] = None) -> int:
        """Start orchestration via set-orchestrate command."""
        cmd = ["set-orchestrate", str(self.config.path)]
        if plan_file:
            cmd.extend(["--plan", plan_file])

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self._orch_proc = proc
            self.orchestrator_pid = proc.pid
            self.orchestrator_started_at = now_iso()
            logger.info(f"[{self.config.name}] Orchestration started, PID={proc.pid}")
            return proc.pid
        except FileNotFoundError:
            logger.error(f"[{self.config.name}] set-orchestrate not found")
            raise

    def stop_orchestration(self):
        """Stop orchestration."""
        self._manually_stopped = True
        if self.orchestrator_pid and _is_alive(self.orchestrator_pid):
            _kill_gracefully(self.orchestrator_pid)
            logger.info(f"[{self.config.name}] Orchestration stopped (PID={self.orchestrator_pid})")
        self.orchestrator_pid = None
        self.orchestrator_started_at = None
        self._orch_proc = None

    def health_check(self) -> list[str]:
        """Check process health. Returns list of actions taken."""
        actions = []

        # Sentinel health — check both process death AND session end
        sentinel_needs_restart = False

        # Python-mode supervisors have completely different lifecycle
        # semantics from Claude sentinels:
        #   - they log to stderr (via logging), not stdout, so stdout-mtime
        #     staleness detection is invalid
        #   - a clean exit (code 0) is the normal path for a completed
        #     orchestration — the Python daemon writes SUPERVISOR_STOP and
        #     exits, and we SHOULD NOT restart it
        #   - the daemon has its own internal crash recovery for the
        #     orchestrator subprocess
        # So for python mode, only auto-restart on a hard process crash
        # (PID gone without a clean exit), never on staleness or clean exit.
        python_mode = self._supervisor_mode() == "python"

        if self.sentinel_pid and not _is_alive(self.sentinel_pid):
            # Process died — but distinguish clean exit from crash.
            clean_exit = False
            if self._sentinel_proc is not None:
                code = self._sentinel_proc.poll()
                if code == 0:
                    clean_exit = True
            if python_mode and clean_exit:
                actions.append(f"python supervisor exited cleanly (pid={self.sentinel_pid})")
                self.sentinel_pid = None
                self._sentinel_proc = None
                # No restart — orchestration is done or was stopped
            else:
                actions.append(f"sentinel died (pid={self.sentinel_pid})")
                self.sentinel_pid = None
                self._sentinel_proc = None
                self.sentinel_crash_count += 1
                sentinel_needs_restart = True

        elif python_mode and self.sentinel_pid:
            # Python supervisor alive — trust it, skip staleness + session
            # end checks. The daemon writes supervisor/status.json which
            # the dashboard can read for liveness detail.
            pass

        elif self.sentinel_pid and self._sentinel_proc:
            # Legacy Claude sentinel — process alive, but check if session
            # ended (claude -p may linger even after end_turn)
            poll_result = self._sentinel_proc.poll()
            if poll_result is not None:
                # Process actually exited
                actions.append(f"sentinel session ended (exit_code={poll_result}, pid={self.sentinel_pid})")
                self.sentinel_pid = None
                self._sentinel_proc = None
                self.sentinel_crash_count += 1
                sentinel_needs_restart = True
            elif self._is_sentinel_session_stale():
                # Process alive but session idle — stdout not updated for >120s
                actions.append(f"sentinel session stale (pid={self.sentinel_pid})")
                _kill_gracefully(self.sentinel_pid)
                self.sentinel_pid = None
                self._sentinel_proc = None
                self.sentinel_crash_count += 1
                sentinel_needs_restart = True

        # Orchestrator health — detect death, flag sentinel restart if needed.
        # When the orchestrator dies (context limit, timeout, crash), the sentinel
        # poll script detects EVENT:process_exit and tries to restart. But if the
        # sentinel session also dies (context limit), it creates a crash-loop:
        # sentinel detects dead PID → exits → manager restarts → no context → loop.
        # Fix: when orchestrator is dead and sentinel is also dead, restart sentinel.
        if self.orchestrator_pid and not _is_alive(self.orchestrator_pid):
            actions.append(f"orchestrator died (pid={self.orchestrator_pid})")
            self.orchestrator_pid = None
            self._orch_proc = None
            # If sentinel is also gone, flag restart so it can recover stalled changes
            if not self.sentinel_pid and not sentinel_needs_restart:
                sentinel_needs_restart = True
                actions.append("orchestrator+sentinel both dead — will restart sentinel for recovery")

        # Unified sentinel restart (triggered by sentinel death OR orchestrator death)
        if sentinel_needs_restart:
            if self._manually_stopped:
                actions.append("sentinel exited — manually stopped, not restarting")
            elif self._is_orchestration_done():
                actions.append("sentinel exited — orchestration done, not restarting")
            elif self.sentinel_crash_count > MAX_CRASH_RESTARTS:
                actions.append(
                    f"sentinel restart limit reached ({MAX_CRASH_RESTARTS}), "
                    "not restarting — manual intervention required"
                )
            elif self.config.auto_restart_sentinel:
                try:
                    self.start_sentinel(spec=self.sentinel_spec)
                    actions.append(f"sentinel auto-restarted (#{self.sentinel_crash_count})")
                except Exception as e:
                    actions.append(f"sentinel restart failed: {e}")

        return actions

    def _is_sentinel_session_stale(self) -> bool:
        """Check if sentinel stdout log hasn't been updated in >120s.

        When a claude -p session ends with end_turn, it stops writing to stdout
        but the process may linger. If stdout hasn't been updated and the
        orchestration is still running, the session is effectively dead.
        """
        try:
            from ..paths import SetRuntime
            sentinel_dir = Path(SetRuntime(str(self.config.path)).sentinel_dir)
        except Exception:
            sentinel_dir = self.config.path / ".set" / "sentinel"

        stdout_log = sentinel_dir / "stdout.log"
        if not stdout_log.is_file():
            return False

        import time
        mtime = stdout_log.stat().st_mtime
        age = time.time() - mtime
        # Stale if no output for 120s AND orchestration is still running
        return age > 120 and not self._is_orchestration_done()

    def _is_orchestration_done(self) -> bool:
        """Check if the orchestration state file shows status=done."""
        import json
        state_file = self.config.path / "orchestration-state.json"
        if not state_file.is_file():
            return False
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            return state.get("status") == "done"
        except (json.JSONDecodeError, OSError):
            return False

    def status(self) -> dict:
        return {
            "name": self.config.name,
            "mode": self.config.mode,
            "path": str(self.config.path),
            "sentinel": {
                "pid": self.sentinel_pid,
                "alive": _is_alive(self.sentinel_pid),
                "started_at": self.sentinel_started_at,
                "spec": self.sentinel_spec,
                "crash_count": self.sentinel_crash_count,
            },
            "orchestrator": {
                "pid": self.orchestrator_pid,
                "alive": _is_alive(self.orchestrator_pid),
                "started_at": self.orchestrator_started_at,
            },
        }
