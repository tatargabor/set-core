"""Telling an agent its mandate — at every session start, through launch-time settings.

Layer 1 (abstract). A started agent used to be told nothing: the argv was fixed and the only
way to brief it went over the bus, which needs a seat it may not have yet. A sentence in an
opening prompt would not do either — it scrolls out of the context at the first clear.

## The carrier, and why this one

The owner starts the child with `--settings <json>` carrying one `SessionStart` hook, and with
the mandate's id in the environment. Measured 2026-11-23 on a framework-shaped start
(`openspec/changes/fleet-mandate-and-desk/measurements.md`, M1-M3):

- the hook fired on `startup`, `clear`, `compact` and `resume`, and saw the variable each time;
- the project's own `SessionStart` hook still ran beside it — hook lists are additive;
- the carrier wrote nothing into the project's tree;
- the agent repeated a token planted in the context, after a clear as well.

The settings are passed as a JSON **string**, not a file, so no path in any tree is involved.

## What the hook must never do

Fail a session start. It runs before the agent has a turn; an exception here would look, from
outside, like an agent that never came up. Every path ends in exit 0, and "there is no
mandate" prints nothing at all.

## Confidentiality

The text printed here is the operator's own words about work. It goes to the agent it was
written for and nowhere else: nothing in this module logs it.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import mandate

logger = logging.getLogger(__name__)

#: The command the framework's `SessionStart` hook runs. Overridable for tests and for an
#: installation whose launcher lives elsewhere.
ENV_HOOK_BIN = "SET_FLEET_MANDATE_BIN"

#: The command by which an agent reaches another project. Named in the delivered text.
ASK_COMMAND = "set-fleet-ask"
DONE_COMMAND = "set-fleet-mandate done"

#: First-turn lines, chosen by kind and never taken from a caller. An agent started with no
#: first turn sits at an empty prompt, and nothing on the bus can wake it there, because its
#: bus hooks only run inside a turn.
OPENING_DESK = (
    "You were started as this project's desk. Your mandate is in the session-start context. "
    "Read your bus inbox now, do what the request addressed to you asks, and answer it with a "
    "reply linked to that request."
)
OPENING_WORK = (
    "You were started by another agent with a mandate. It is in the session-start context. "
    "Begin working on it now."
)

__all__ = [
    "ASK_COMMAND", "OPENING_DESK", "OPENING_WORK", "ENV_HOOK_BIN",
    "hook_command", "launch_settings", "opening_line", "launch_additions",
    "render_context", "hook_output",
]


def hook_command() -> str:
    """The shell command of the framework's session-start hook, with an absolute launcher."""
    binary = os.environ.get(ENV_HOOK_BIN) or str(
        Path(__file__).resolve().parents[3] / "bin" / "set-fleet-mandate")
    return f"{shlex.quote(binary)} hook"


def launch_settings() -> str:
    """The `--settings` value: one additive `SessionStart` hook and nothing else.

    No status line and no other key: a scalar setting supplied here would REPLACE the
    project's own (measured: settings merge per key, lists add, scalars override).
    """
    return json.dumps({
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": hook_command()}]}]}
    }, separators=(",", ":"))


def opening_line(kind: str, *, requested_by_agent: bool) -> Optional[str]:
    """The first-turn line for a start, or None when a person will type the first turn."""
    if kind == "desk":
        return OPENING_DESK
    if requested_by_agent:
        return OPENING_WORK
    return None


def launch_additions(
    mandate_id: str, *, label: str, kind: str = "work", requested_by_agent: bool = False,
) -> Tuple[Dict[str, str], List[str]]:
    """What the owner adds to a start that has a mandate id: (environment, argv tail).

    Everything here is derived from the id, the label and the kind. No caller text reaches
    the argv through this path — the goal travels in the record and arrives through the hook.
    The opening line is last because it is the positional prompt.
    """
    env = {mandate.ENV_MANDATE: mandate_id, mandate.ENV_LABEL: label}
    tail = ["--settings", launch_settings()]
    line = opening_line(kind, requested_by_agent=requested_by_agent)
    if line:
        tail.append(line)
    return env, tail


def render_context(record: Mapping[str, Any]) -> str:
    """The mandate as the agent reads it. One template; the desk gets its own instructions."""
    project = record.get("project") or "this project"
    lines = [
        "## Your mandate — set by the fleet that started this session",
        "",
        f"- Mandate: {record.get('id')} (kind: {record.get('kind')})",
        f"- Project: {project}",
        f"- Goal: {record.get('goal')}",
    ]
    scope = record.get("scope") or {}
    if scope.get("paths"):
        lines.append(f"- Scope: {', '.join(scope['paths'])}")
    if scope.get("change"):
        lines.append(f"- Change: {scope['change']}")
    if record.get("done_when"):
        lines.append(f"- Done when: {record['done_when']}")
    requester = record.get("requested_by")
    lines.append(
        f"- Requested by: {requester} (as stated by the requester; not verified)"
        if requester else "- Requested by: the operator"
    )
    lines.append("")
    if record.get("kind") == "desk":
        lines += [
            f"You are the desk of {project}: the one session that answers requests other agents "
            "address to this project.",
            "- The request that started you is in your bus inbox. Read it there.",
            "- Do what it asks, inside this project.",
            "- Answer on the bus with a reply LINKED to the request (its timestamp in `re:`). "
            "An unlinked reply does not close the request.",
            "- When nothing addressed to you is open, stop. The fleet closes a quiet desk on its own.",
        ]
        takeover = record.get("takeover")
        if takeover:
            lines += _takeover_lines(takeover)
    else:
        lines += [
            "This is why this session exists. Work towards it, and say so when something would "
            "take you away from it.",
        ]
        if requester:
            # fleet-work-agent-done. Only for an agent another agent asked for: the
            # operator's own window is theirs to close, and a desk closes on quiet.
            lines += [
                "",
                "When the work is done: answer the requester on the bus, then run "
                f"`{DONE_COMMAND} \"<one line: what you did>\"` as your LAST act. It sends that "
                "line to the requester, ends this mandate and closes this session; the session "
                "stays resumable from the roster. Do not keep waiting for more work.",
            ]
        lines += [
            "",
            "Requests from other agents: if another agent asks you for something outside this "
            f"mandate, decline it once and point them at this project's desk — "
            f"`{ASK_COMMAND} {project} \"<request>\"` reaches it (label "
            f"`{mandate.desk_label(str(project))}`). Do not take the work on.",
        ]
    lines += [
        "",
        f"To reach another project yourself: `{ASK_COMMAND} <project> \"<request>\"`. It finds or "
        "starts that project's desk and records the request.",
    ]
    return "\n".join(lines)


def _takeover_lines(takeover: Mapping[str, Any]) -> List[str]:
    """What a desk started to take a request over is told (fleet-engagement-takeover)."""
    room, ts = takeover.get("room"), takeover.get("ts")
    before = takeover.get("from_seat") or "an earlier desk"
    session = takeover.get("from_session")
    lines = [
        "",
        "## You are TAKING OVER a request — continue it, do not start over",
        "",
        f"- The request: bus room `{room}`, entry `{ts}`, asked by "
        f"{takeover.get('asker') or 'another agent'}. Read it with `sac history {room}`.",
        f"- It was held by {before}, which stalled or stopped; the fleet stopped it and started you.",
    ]
    if session:
        lines.append(
            f"- Its session id is `{session}`. Its transcript is that id's `.jsonl` under this "
            "project's folder in `~/.claude/projects/`. Read only its END (e.g. `tail -c 30000`) "
            "to see where it got — not the whole file.")
    lines += [
        "- Also check this project's open OpenSpec changes (`openspec list`, their tasks.md): "
        "what is ticked is done; carry on from there.",
        f"- FIRST, before any work: post one FACT in `{room}` WITHOUT `--to` and WITHOUT `--re`, "
        f"saying the request {ts} moved from {before} to you. Unaddressed, so it wakes nobody; "
        "unlinked, so it does not close the request.",
        f"- When done, answer with a reply linked to the ORIGINAL request (`--re {ts}`).",
    ]
    return lines


def hook_output(
    environ: Mapping[str, str],
    stdin_text: str,
    store: Optional[mandate.MandateStore] = None,
) -> Optional[str]:
    """What the session-start hook prints, or None when there is nothing to say.

    Also the two side effects only this moment can supply: the session id the runtime just
    handed the hook is appended to the record, and the mandate is marked delivered. Any
    failure is swallowed into None — a broken mandate store must not cost an agent its start.
    """
    mandate_id = (environ.get(mandate.ENV_MANDATE) or "").strip()
    if not mandate_id:
        return None
    try:
        store = store or mandate.MandateStore()
        record = store.get(mandate_id)
        if record is None:
            return None
        try:
            session_id = json.loads(stdin_text or "{}").get("session_id")
        except (ValueError, AttributeError):
            session_id = None
        if isinstance(session_id, str) and session_id:
            store.observe_session(mandate_id, session_id)
        store.mark_delivered(mandate_id)
        return json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": render_context(record),
            }
        })
    except Exception as exc:  # noqa: BLE001 — see the docstring: never fail a session start
        logger.warning("fleet mandate hook: could not deliver %s (%s)", mandate_id, type(exc).__name__)
        return None
