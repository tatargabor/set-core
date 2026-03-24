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
        self.sentinel_crash_count: int = 0
        self.orchestrator_pid: Optional[int] = None
        self.orchestrator_started_at: Optional[str] = None
        self._sentinel_proc: Optional[subprocess.Popen] = None
        self._orch_proc: Optional[subprocess.Popen] = None

    def _load_sentinel_prompt(self, spec: Optional[str] = None) -> str:
        """Load sentinel skill file as prompt, with fallback to hardcoded prompt."""
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

        if spec:
            prompt += f"\n\nArguments: --spec {spec}"

        return prompt

    def start_sentinel(self, spec: Optional[str] = None) -> int:
        """Spawn sentinel as a dedicated claude agent process."""
        prompt = self._load_sentinel_prompt(spec=spec)
        # Log stdout and stderr to files for debugging
        try:
            from ..paths import SetRuntime
            sentinel_log = Path(SetRuntime(str(self.config.path)).sentinel_dir)
        except Exception:
            sentinel_log = self.config.path / ".set" / "sentinel"
        sentinel_log.mkdir(parents=True, exist_ok=True)
        stdout_path = sentinel_log / "stdout.log"
        stderr_file = open(sentinel_log / "stderr.log", "w")

        # Use 'script' to force line-buffered output from claude CLI
        # script -qfc "cmd" file — runs cmd in a pty, writes to file
        cmd = [
            "script", "-qfc",
            "claude -p --max-turns 500 --dangerously-skip-permissions",
            str(stdout_path),
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.path),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                start_new_session=True,
            )
            # Send prompt via stdin — avoids command-line length limits
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
            self._sentinel_proc = proc
            self.sentinel_pid = proc.pid
            self.sentinel_started_at = now_iso()
            self.sentinel_spec = spec
            self.sentinel_crash_count = 0
            logger.info(f"[{self.config.name}] Sentinel started, PID={proc.pid}")
            return proc.pid
        except FileNotFoundError:
            logger.error(f"[{self.config.name}] claude CLI not found")
            raise

    def stop_sentinel(self):
        """Gracefully stop sentinel agent and its child processes (orchestrator etc.)."""
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
        if self.orchestrator_pid and _is_alive(self.orchestrator_pid):
            _kill_gracefully(self.orchestrator_pid)
            logger.info(f"[{self.config.name}] Orchestration stopped (PID={self.orchestrator_pid})")
        self.orchestrator_pid = None
        self.orchestrator_started_at = None
        self._orch_proc = None

    def health_check(self) -> list[str]:
        """Check process health. Returns list of actions taken."""
        actions = []

        # Sentinel health
        if self.sentinel_pid and not _is_alive(self.sentinel_pid):
            actions.append(f"sentinel died (pid={self.sentinel_pid})")
            self.sentinel_pid = None
            self._sentinel_proc = None
            self.sentinel_crash_count += 1

            if (self.config.auto_restart_sentinel
                    and self.sentinel_crash_count <= MAX_CRASH_RESTARTS
                    and not self._is_orchestration_done()):
                try:
                    self.start_sentinel(spec=self.sentinel_spec)
                    actions.append(f"sentinel auto-restarted (crash #{self.sentinel_crash_count})")
                except Exception as e:
                    actions.append(f"sentinel restart failed: {e}")
            elif self._is_orchestration_done():
                actions.append("sentinel exited — orchestration done, not restarting")
            elif self.sentinel_crash_count > MAX_CRASH_RESTARTS:
                actions.append(
                    f"sentinel restart limit reached ({MAX_CRASH_RESTARTS}), "
                    "not restarting — manual intervention required"
                )

        # Orchestrator health (no auto-restart, just detect)
        if self.orchestrator_pid and not _is_alive(self.orchestrator_pid):
            actions.append(f"orchestrator died (pid={self.orchestrator_pid})")
            self.orchestrator_pid = None
            self._orch_proc = None

        return actions

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
