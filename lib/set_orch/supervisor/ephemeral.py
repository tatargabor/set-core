"""Ephemeral Claude subprocess helper.

Phase 1 ships the skeleton: signature, safe subprocess invocation, log
capture, timeout handling. Phase 2 will add the trigger-specific prompt
builders (crash, integration-failed, stall, canary) and history summary
feeds.

Design principles:

- **Every invocation is fresh** — no `--resume`, no session_id carried
  across spawns. History is passed in the prompt as a daemon-assembled
  summary (see history.py in Phase 2).
- **Bounded budget** — default timeout 10 min, default max-turns 25.
  A single trigger should never consume more than a focused task's
  worth of tokens.
- **Deterministic** — the prompt is built by the daemon, not by a
  previous Claude conversation. Same trigger + same state = same
  prompt = same decision (modulo LLM randomness).
- **Fail-safe on error** — timeout, non-zero exit, etc. are logged as
  events but do NOT crash the daemon. The trigger that spawned the
  Claude is retried per its retry budget (Phase 2).
"""

from __future__ import annotations

import datetime
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EphemeralResult:
    """Result of a single `claude -p` ephemeral spawn."""
    trigger: str
    exit_code: int
    timed_out: bool
    elapsed_ms: int
    stdout_path: str = ""
    stderr_path: str = ""
    stdout_tail: str = ""  # last ~2KB of stdout for event emission


def spawn_ephemeral_claude(
    *,
    trigger: str,
    prompt: str,
    cwd: str,
    project_path: str,
    model: str = "",
    timeout: int = 600,
    max_turns: int = 25,
    allow_all_tools: bool = True,
    prior_attempts_summary: Optional[str] = None,
) -> EphemeralResult:
    """Spawn a fresh `claude -p` subprocess for a single focused task.

    Args:
        trigger: short name for the trigger type (e.g. "integration_failed",
            "crash", "canary", "final_report"). Used for log file naming
            and event emission.
        prompt: the full prompt the Claude receives via stdin. Should already
            contain the stable header + variable body + question pattern.
        cwd: working directory for the subprocess (usually the project path).
        project_path: the project root — used to place log files under
            `.set/supervisor/claude-logs/`.
        model: claude model short name. Empty string (default) resolves
            via model_config.resolve_model("supervisor"). Operator can
            override per-trigger via models.trigger.<type> in the yaml.
        timeout: wall-clock seconds before the subprocess is killed.
        max_turns: maximum `claude -p --max-turns` budget.
        allow_all_tools: pass `--dangerously-skip-permissions` (required
            for the subprocess to invoke Bash, Read, etc. without asking).
        prior_attempts_summary: optional pre-built summary of prior attempts
            for this trigger type + change (Phase 2 uses this; Phase 1
            ignores it unless the caller wants to prepend it manually).

    Returns:
        EphemeralResult with exit code, elapsed time, and log paths.
    """
    if not model:
        from ..model_config import resolve_model
        model = resolve_model("supervisor", project_dir=project_path)
    started = datetime.datetime.now()
    ts = started.strftime("%Y%m%d-%H%M%S")
    log_dir = Path(project_path) / ".set" / "supervisor" / "claude-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{trigger}-{ts}.stdout.log"
    stderr_path = log_dir / f"{trigger}-{ts}.stderr.log"

    # Prepend prior-attempts summary if provided
    effective_prompt = prompt
    if prior_attempts_summary:
        effective_prompt = (
            f"<<<PRIOR ATTEMPTS — do not repeat these>>>\n"
            f"{prior_attempts_summary}\n"
            f"<<<END PRIOR ATTEMPTS>>>\n\n"
            f"{prompt}"
        )

    cmd = ["claude", "-p", "--model", model, "--max-turns", str(max_turns)]
    if allow_all_tools:
        cmd.append("--dangerously-skip-permissions")

    # Inject set-core bin on PATH so the ephemeral Claude can call
    # set-sentinel-finding, set-sentinel-status, etc.
    env = os.environ.copy()
    set_core_bin = Path(__file__).resolve().parent.parent.parent.parent / "bin"
    if set_core_bin.is_dir():
        env["PATH"] = f"{set_core_bin}:{env.get('PATH', '')}"

    timed_out = False
    exit_code = -1
    try:
        with open(stdout_path, "wb") as so, open(stderr_path, "wb") as se:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=so,
                stderr=se,
                env=env,
            )
            try:
                proc.communicate(input=effective_prompt.encode("utf-8"), timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                logger.warning("Ephemeral Claude[%s] timed out after %ds — killing", trigger, timeout)
                timed_out = True
                proc.kill()
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                exit_code = -9
    except FileNotFoundError:
        logger.error("Ephemeral Claude[%s] failed: claude CLI not found on PATH", trigger)
        exit_code = -127
    except Exception as exc:
        logger.exception("Ephemeral Claude[%s] unexpected error: %s", trigger, exc)
        exit_code = -1

    elapsed_ms = int((datetime.datetime.now() - started).total_seconds() * 1000)

    # Read last 2KB of stdout for event emission
    tail = ""
    try:
        if stdout_path.is_file():
            size = stdout_path.stat().st_size
            with open(stdout_path, "rb") as f:
                f.seek(max(0, size - 2048))
                tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        pass

    logger.info(
        "Ephemeral Claude[%s] done exit=%d timed_out=%s elapsed=%dms stdout=%s",
        trigger, exit_code, timed_out, elapsed_ms, stdout_path,
    )
    return EphemeralResult(
        trigger=trigger,
        exit_code=exit_code,
        timed_out=timed_out,
        elapsed_ms=elapsed_ms,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        stdout_tail=tail,
    )
