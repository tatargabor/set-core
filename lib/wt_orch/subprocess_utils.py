"""Type-safe subprocess wrappers for claude, git, and generic commands.

All invocations are logged with: cmd, duration_ms, exit_code, output_size.
Returns dataclass results instead of raising exceptions — callers decide
how to handle non-zero exit codes.
"""

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a generic subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


@dataclass
class ClaudeResult(CommandResult):
    """Result of a Claude CLI invocation."""

    pass


@dataclass
class GitResult(CommandResult):
    """Result of a git CLI invocation."""

    pass


def _truncate_output(output: str, max_size: int) -> str:
    """Truncate output from the beginning, keeping the tail."""
    if len(output) <= max_size:
        return output
    marker = f"[...truncated, showing last {max_size} bytes...]\n"
    return marker + output[-max_size:]


def run_command(
    cmd: list[str],
    *,
    timeout: int | None = None,
    cwd: str | Path | None = None,
    max_output_size: int = 1024 * 1024,  # 1MB
    env: dict[str, str] | None = None,
    stdin_data: str | None = None,
) -> CommandResult:
    """Execute a command with timeout and output capture.

    Args:
        cmd: Command and arguments as list.
        timeout: Timeout in seconds. None for no timeout.
        cwd: Working directory.
        max_output_size: Max bytes to keep from output (keeps tail).
        env: Additional environment variables (merged with os.environ).
        stdin_data: Data to send to stdin.

    Returns:
        CommandResult with exit_code, stdout, stderr, duration_ms, timed_out.
    """
    import os

    full_env = None
    if env:
        full_env = {**os.environ, **env}

    start = time.monotonic()
    timed_out = False

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=full_env,
            input=stdin_data,
        )
        stdout = _truncate_output(proc.stdout or "", max_output_size)
        stderr = _truncate_output(proc.stderr or "", max_output_size)
        exit_code = proc.returncode

    except subprocess.TimeoutExpired as e:
        timed_out = True
        stdout = _truncate_output(e.stdout or "" if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", errors="replace"), max_output_size)
        stderr = _truncate_output(e.stderr or "" if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", errors="replace"), max_output_size)
        exit_code = -1

    except FileNotFoundError:
        stdout = ""
        stderr = f"Command not found: {cmd[0]}"
        exit_code = 127

    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "command_completed",
        extra={
            "cmd": " ".join(cmd[:3]),  # first 3 args for brevity
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "output_size": len(stdout),
            "timed_out": timed_out,
        },
    )

    return CommandResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
    )


def run_claude(
    prompt: str,
    *,
    timeout: int = 300,
    model: str | None = None,
    extra_args: list[str] | None = None,
    cwd: str | Path | None = None,
) -> ClaudeResult:
    """Execute Claude CLI with prompt on stdin.

    Migrated from: run_claude() in wt-common.sh

    Args:
        prompt: The prompt text to send via stdin.
        timeout: Timeout in seconds (default 300 = 5 min).
        model: Model short name (e.g., "sonnet", "opus").
        extra_args: Additional CLI arguments.
        cwd: Working directory.

    Returns:
        ClaudeResult with exit_code, stdout, stderr, duration_ms, timed_out.
    """
    cmd = ["claude", "-p"]

    if model:
        cmd.extend(["--model", model])

    if extra_args:
        cmd.extend(extra_args)

    logger.debug(
        "run_claude",
        extra={
            "prompt_size": len(prompt),
            "timeout": timeout,
            "model": model or "default",
        },
    )

    result = run_command(
        cmd,
        timeout=timeout,
        cwd=cwd,
        stdin_data=prompt,
    )

    return ClaudeResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
    )


def run_git(*args: str, cwd: str | Path | None = None, timeout: int = 60) -> GitResult:
    """Execute a git command.

    Args:
        *args: Git subcommand and arguments (e.g., "log", "--oneline", "-5").
        cwd: Working directory.
        timeout: Timeout in seconds (default 60).

    Returns:
        GitResult with exit_code, stdout, stderr, duration_ms.
    """
    cmd = ["git"] + list(args)

    result = run_command(cmd, timeout=timeout, cwd=cwd)

    if result.exit_code != 0:
        logger.warning(
            "git_failed",
            extra={
                "cmd": " ".join(cmd),
                "exit_code": result.exit_code,
                "stderr": result.stderr[:200] if result.stderr else "",
            },
        )

    return GitResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
    )
