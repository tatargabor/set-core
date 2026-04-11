"""Build prior-attempts summaries for ephemeral Claude prompts.

Each ephemeral Claude is fresh — no `--resume`, no session id carried
across spawns. To give a triggered Claude the relevant history of prior
attempts for the same (trigger_type, change) pair, the daemon reads
SUPERVISOR_TRIGGER events from the orchestration events log and
assembles a compact text summary.

The summary is intentionally short: timestamp, exit code, the first
non-empty line of the trigger output (which usually contains the verdict
or finding ID), and the trigger reason. The downstream prompt builder
prepends this summary to the variable body so the new Claude can see
"this is the 3rd time we tried X, here's what failed" without burning
tokens on a full conversation history.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PriorAttempt:
    """One entry from the SUPERVISOR_TRIGGER history."""
    ts: str
    trigger: str
    change: str
    reason: str
    exit_code: int
    timed_out: bool
    summary: str            # truncated stdout tail for the prompt


def build_prior_attempts_summary(
    events_path: Path,
    *,
    trigger: str,
    change: str = "",
    max_attempts: int = 5,
) -> str:
    """Read SUPERVISOR_TRIGGER events and produce a prompt-friendly text summary.

    Args:
        events_path: path to orchestration-events.jsonl
        trigger:     trigger type to filter by (e.g. "integration_failed")
        change:      change name to filter by (empty = match any)
        max_attempts: keep only the most recent N attempts in the summary

    Returns:
        A short human-readable text block, or "" if there are no prior
        attempts. Callers may prepend this to a trigger prompt body.
    """
    attempts = _load_prior_attempts(
        events_path, trigger=trigger, change=change, limit=max_attempts,
    )
    if not attempts:
        return ""
    lines = [f"Prior {trigger} attempts ({len(attempts)} most recent):"]
    for a in attempts:
        scope = f" change={a.change}" if a.change else ""
        outcome = "timeout" if a.timed_out else f"exit={a.exit_code}"
        head_lines = (a.summary or "").strip().splitlines()
        head = head_lines[0] if head_lines else ""
        lines.append(
            f"  - {a.ts}{scope} reason={a.reason!r} outcome={outcome} : {head[:160]}"
        )
    return "\n".join(lines)


def _load_prior_attempts(
    events_path: Path,
    *,
    trigger: str,
    change: str,
    limit: int,
) -> list[PriorAttempt]:
    """Load matching SUPERVISOR_TRIGGER events from the JSONL log.

    Skipped triggers (where the daemon recorded a SUPERVISOR_TRIGGER event
    with `skipped=...` instead of an exit_code) are ignored — they don't
    represent actual prior attempts.
    """
    if not events_path.is_file():
        return []
    out: list[PriorAttempt] = []
    try:
        with open(events_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") != "SUPERVISOR_TRIGGER":
                    continue
                data = ev.get("data") or {}
                if data.get("trigger") != trigger:
                    continue
                if change and data.get("change") and data["change"] != change:
                    continue
                if "skipped" in data and "exit_code" not in data:
                    continue
                out.append(PriorAttempt(
                    ts=str(ev.get("ts", "")),
                    trigger=str(data.get("trigger", "")),
                    change=str(data.get("change", "")),
                    reason=str(data.get("reason", "")),
                    exit_code=int(data.get("exit_code", 0) or 0),
                    timed_out=bool(data.get("timed_out", False)),
                    summary=str(data.get("stdout_tail", ""))[-512:],
                ))
    except OSError as exc:
        logger.warning("Could not read events file %s: %s", events_path, exc)
        return []
    return out[-limit:]
