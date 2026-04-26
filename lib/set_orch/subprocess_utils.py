from __future__ import annotations

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

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0
    cost_usd: float = 0.0


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
            errors="replace",
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


_MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    # `opus` shorthand currently resolves to 4.7 (the latest release).
    # Operators concerned about token economy on 4.7 (~1.5-2× the output
    # of 4.6 for similar quality) can pin `opus-4-6` explicitly in
    # orchestration config: `default_model: opus-4-6`. We expect to
    # revisit the default after collecting more comparative run data.
    "opus": "claude-opus-4-7",
    "opus-1m": "claude-opus-4-7[1m]",
    "sonnet-1m": "claude-sonnet-4-6[1m]",
    # Explicit version pins — bypass the shorthand default.
    "opus-4-6": "claude-opus-4-6",
    "opus-4-7": "claude-opus-4-7",
    "opus-4-6-1m": "claude-opus-4-6[1m]",
    "opus-4-7-1m": "claude-opus-4-7[1m]",
}


def resolve_model_id(name: str) -> str:
    """Resolve short model name to full Claude model ID.

    Mirrors resolve_model_id() in set-common.sh.
    """
    return _MODEL_MAP.get(name, name)


def _extract_text_from_json_output(raw: str) -> str:
    """Extract assistant text from Claude CLI ``--verbose --output-format json``.

    Workaround for Claude Code >=2.1.83 bug where the ``result`` field in the
    final JSON object is empty when extended thinking is enabled, even though
    the assistant DID produce text in earlier streaming messages.

    The verbose JSON output is a JSON array of event objects.  We look for
    assistant messages with text content blocks.  Falls back to the ``result``
    field if non-empty.
    """
    import json as _json

    texts: list[str] = []
    result_text = ""

    # Try parsing as JSON array first (--verbose --output-format json)
    items: list[dict] = []
    try:
        data = _json.loads(raw)
        items = data if isinstance(data, list) else [data]
    except _json.JSONDecodeError:
        # Fallback: try JSONL (one JSON object per line)
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(_json.loads(line))
            except _json.JSONDecodeError:
                continue
    if not items:
        return ""

    for obj in items:
        if not isinstance(obj, dict):
            continue

        # Final result object — use if non-empty
        if obj.get("type") == "result" and obj.get("result"):
            result_text = obj["result"]

        # Assistant message with content blocks
        if obj.get("type") == "assistant":
            msg = obj.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "text" and block.get("text"):
                    texts.append(block["text"])

    return result_text if result_text else "\n".join(texts)


def _extract_usage_from_json_output(raw: str) -> dict:
    """Extract token usage from Claude CLI JSON output's result object."""
    import json as _json
    try:
        data = _json.loads(raw)
        items = data if isinstance(data, list) else [data]
    except _json.JSONDecodeError:
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                items = [_json.loads(line)]
                break
            except _json.JSONDecodeError:
                continue
        else:
            return {}
    for obj in reversed(items):
        if not isinstance(obj, dict) or obj.get("type") != "result":
            continue
        usage = obj.get("usage", {})
        if usage:
            return {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_create_tokens": usage.get("cache_creation_input_tokens", 0),
                "cost_usd": obj.get("total_cost_usd", 0.0) or 0.0,
            }
    return {}


def run_claude(
    prompt: str,
    *,
    timeout: int = 300,
    model: str | None = None,
    extra_args: list[str] | None = None,
    cwd: str | Path | None = None,
) -> ClaudeResult:
    """Execute Claude CLI with prompt on stdin.

    Migrated from: run_claude() in set-common.sh

    Uses ``--output-format json`` and parses the streaming JSON to extract
    assistant text.  This works around a Claude Code >=2.1.83 bug where
    ``-p`` text mode returns an empty string when extended thinking is active.

    Args:
        prompt: The prompt text to send via stdin.
        timeout: Timeout in seconds (default 300 = 5 min).
        model: Model short name (e.g., "sonnet", "opus") or full ID.
        extra_args: Additional CLI arguments.
        cwd: Working directory.

    Returns:
        ClaudeResult with exit_code, stdout, stderr, duration_ms, timed_out.
    """
    cmd = ["claude", "-p", "--verbose", "--output-format", "json"]

    if model:
        cmd.extend(["--model", resolve_model_id(model)])

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

    # Extract text and usage from JSON output
    raw_stdout = result.stdout
    stdout = raw_stdout
    usage = {}
    if result.exit_code == 0 and raw_stdout.strip():
        extracted = _extract_text_from_json_output(raw_stdout)
        if extracted:
            stdout = extracted
        usage = _extract_usage_from_json_output(raw_stdout)

    return ClaudeResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_read_tokens=usage.get("cache_read_tokens", 0),
        cache_create_tokens=usage.get("cache_create_tokens", 0),
        cost_usd=usage.get("cost_usd", 0.0),
    )


def run_claude_logged(
    prompt: str,
    *,
    purpose: str,
    change: str = "",
    timeout: int = 300,
    model: str | None = None,
    extra_args: list[str] | None = None,
    cwd: str | Path | None = None,
) -> ClaudeResult:
    """Execute Claude CLI, emit LLM_CALL event, and write a verdict sidecar.

    Thin wrapper around run_claude() that:
      1. tags the prompt with [PURPOSE:<purpose>:<change>] so the session
         JSONL can be matched back to its caller
      2. emits an LLM_CALL event so the call is visible in set-web
      3. writes a default `<session_id>.verdict.json` sidecar based on
         the Claude process exit code

    The sidecar is the single source of truth the dashboard reads — see
    `lib/set_orch/gate_verdict.py` and `api/sessions.py::_session_outcome`.
    Gates that produce a richer verdict (review, spec_verify) call
    `persist_gate_verdict` themselves AFTER this function returns; that
    second write overwrites the default sidecar atomically (rename), so
    the more specific source/critical_count wins. Sessions that don't get
    a richer verdict still have the coarse exit-code-based sidecar so the
    UI never falls back to a heuristic outcome.

    Args:
        prompt: The prompt text to send via stdin.
        purpose: Why this call is made (review, smoke_fix, spec_verify,
                 classify, replan, decompose, digest, audit, build_fix, …).
                 Used as the `gate` field in the sidecar.
        change: Change name if call is change-scoped, empty for global calls.
        timeout: Timeout in seconds (default 300 = 5 min).
        model: Model short name or full ID.
        extra_args: Additional CLI arguments.
        cwd: Working directory. If unset, the sidecar cannot be written
            (no Claude session dir to look in) and the caller must rely
            on the gate's own sidecar persistence.
    """
    # Prepend PURPOSE header so _derive_session_label() can identify the call
    tagged_prompt = f"[PURPOSE:{purpose}:{change}]\n{prompt}"

    # Snapshot the Claude session dir before the call so we can locate
    # the session JSONL the call is about to create.
    session_baseline: set[str] = set()
    if cwd:
        try:
            from .gate_verdict import snapshot_session_files
            session_baseline = snapshot_session_files(str(cwd))
        except Exception:
            logger.debug("snapshot_session_files failed", exc_info=True)

    result = run_claude(
        tagged_prompt,
        timeout=timeout,
        model=model,
        extra_args=extra_args,
        cwd=cwd,
    )

    # Emit event (best-effort — never fail the call because of logging)
    try:
        from .events import event_bus
        event_bus.emit("LLM_CALL", change=change, data={
            "purpose": purpose,
            "model": model or "default",
            "duration_ms": result.duration_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cache_read_tokens": result.cache_read_tokens,
            "cache_create_tokens": result.cache_create_tokens,
            "cost_usd": result.cost_usd,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
        })
    except Exception:
        logger.debug("Failed to emit LLM_CALL event", exc_info=True)

    # Write default verdict sidecar from exit code (best-effort).
    if cwd:
        try:
            from .gate_verdict import persist_gate_verdict
            verdict = "pass" if result.exit_code == 0 and not result.timed_out else "fail"
            summary = (
                f"claude exit={result.exit_code} timed_out={result.timed_out}"
                if verdict == "fail"
                else f"claude exit=0 elapsed_ms={result.duration_ms}"
            )
            persist_gate_verdict(
                cwd=str(cwd),
                baseline=session_baseline,
                change_name=change,
                gate=purpose,
                verdict=verdict,
                critical_count=0 if verdict == "pass" else 1,
                source="claude_exit_code",
                summary=summary,
            )
        except Exception:
            logger.debug("Default verdict sidecar persist failed", exc_info=True)

    return result


def detect_default_branch(repo_path: str | Path | None = None) -> str:
    """Detect the default branch name (main, master, etc.) for a repo.

    Checks: symbolic-ref origin/HEAD → show-ref main → show-ref master → "main".
    """
    # Try origin/HEAD first (most reliable for cloned repos)
    r = run_command(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        timeout=5, cwd=str(repo_path) if repo_path else None,
    )
    if r.exit_code == 0 and r.stdout.strip():
        return r.stdout.strip().replace("refs/remotes/origin/", "")

    # Local branch detection
    for name in ("main", "master"):
        r = run_command(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],
            timeout=5, cwd=str(repo_path) if repo_path else None,
        )
        if r.exit_code == 0:
            return name

    return "main"  # default assumption


def run_git(
    *args: str,
    cwd: str | Path | None = None,
    timeout: int = 60,
    best_effort: bool = False,
) -> GitResult:
    """Execute a git command.

    Args:
        *args: Git subcommand and arguments (e.g., "log", "--oneline", "-5").
        cwd: Working directory.
        timeout: Timeout in seconds (default 60).
        best_effort: If True, suppress the WARNING log on non-zero exit.
            Use for calls where failure is an expected/valid scenario
            (e.g., `fetch origin` in a project without a remote).

    Returns:
        GitResult with exit_code, stdout, stderr, duration_ms.
    """
    cmd = ["git"] + list(args)

    result = run_command(cmd, timeout=timeout, cwd=cwd)

    if result.exit_code != 0 and not best_effort:
        _stderr_snippet = (result.stderr[:200] if result.stderr else "").strip()
        logger.warning(
            "git_failed: %s (exit=%d) %s",
            " ".join(cmd), result.exit_code, _stderr_snippet,
        )

    return GitResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
    )
