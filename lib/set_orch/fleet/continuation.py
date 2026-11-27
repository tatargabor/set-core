"""Continue a finished session from the relay channel (B-190).

The carrier is an ASYNCHRONOUS `Stop` hook (`asyncRewake: true`,
`bin/set-hook-continue-relay`). Measured on Claude Code 2.1.330, 2026-11-22:

- such a hook runs beside the idle prompt, and its exit 2 wakes the idle session with its
  stderr as an instruction, so the terminal is never held;
- the runtime does NOT cancel it when the owner types a new prompt (two armed hooks both
  woke the session, the first already stale), so this module supersedes itself;
- the woken turn ends with `stop_hook_active: true`, and `UserPromptSubmit` fires for the
  wake with a `<task-notification>` prompt;
- Claude Code's own suggested next prompt is not reachable from a hook, so the suggestions
  come from one headless model call, labelled as suggestions.

The rules shared with the question relay hold: every failure ends in today's behaviour (the
session simply stays idle), the configuration is never completed by guess, and no summary,
suggestion, or answer text is persisted or logged. That text lives only in the envelope
handed to the outbound.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import local_config
from . import question_relay as qr
from . import wait_detect as wd

logger = logging.getLogger(__name__)

#: Off only when explicitly false: the continuation is part of the relay the switch turns on.
KEY_CONTINUE = "question_relay.continue_enabled"
VERDICT_WAIT_S = 75.0            # covers the wait detector's own 60 s hook entry
VERDICT_POLL_S = 1.0
SUGGEST_TIMEOUT_S = 40
MAX_NEXT = 3
NEXT_MARK = "→ "

SUGGEST_PROMPT = """You read the final message an AI coding agent sent before ending its turn.
The user is away from the terminal and decides on their phone what the agent does next.
Answer in exactly this format and nothing else:
SUMMARY: <one or two sentences: what the turn reported, in the message's own language>
NEXT: <one concrete next instruction the user might give, imperative, at most 80 characters>
GOAL: <what the session was started for, from the OPENING PROMPT below, at most 120 characters>
Give zero to three NEXT lines; none when nothing sensible follows. Leave out GOAL when the
opening prompt does not show it. An agent's "done" is often local (one step, one board): when
the goal looks larger than what the message reports, let a NEXT line carry the goal forward.

MESSAGE:
"""
GOAL_PROMPT = "\n\nOPENING PROMPT (why the session was started):\n"
KEEP_GOING = "Keep going toward the original goal"
OPENING_MAX = 800
OPENING_HEAD_LINES = 400
GOAL_MAX = 200
# Entries whose text is the runtime's or a hook's, not the person's (B-246's lesson: a wrapper
# read as the owner's words is a false quote).
_NOT_OWN = ("<command-", "<local-command-", "<task-notification", "<system-reminder", "Caveat:",
            "[Request interrupted")

Suggester = Callable[[str], Optional[Tuple[str, List[str]]]]


def supersede_path(session_id: str, base: Optional[Path] = None) -> Path:
    # Outside `waiting/` on purpose: the bridge reads every `.json` there as a waiting call.
    return (base or qr.state_dir()) / "supersede" / f"{qr._safe_id(session_id)}"


def mark_superseded(session_id: str, base: Optional[Path] = None, wall: Callable[[], float] = time.time) -> None:
    """The owner typed a prompt (`UserPromptSubmit`): any continuation armed before now is stale.

    Also removes a waiting continuation record at once, so the bridge closes the post
    without waiting for the carrier's next poll. Never touches a permission or question
    record: a prompt cannot be typed while those block.
    """
    base = base or qr.state_dir()
    if not qr._safe_id(session_id):
        return
    path = supersede_path(session_id, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(repr(wall()), encoding="utf-8")
    try:
        record = json.loads(qr.waiting_path(session_id, base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(record, dict) and record.get("kind") == qr.KIND_CONTINUATION:
        qr._clear_waiting(session_id, base)
        logger.info("continuation [%s]: superseded by a prompt; record removed", qr._safe_id(session_id)[:8])


def _superseded_since(session_id: str, armed: float, base: Path) -> bool:
    try:
        return float(supersede_path(session_id, base).read_text(encoding="utf-8")) >= armed
    except (OSError, ValueError):
        return False


def _epoch(stamp: Any) -> Optional[float]:
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def moved_on(entries: List[Dict[str, Any]], armed: float) -> bool:
    """Whether the session produced an assistant entry after the continuation was armed.

    Catches wakes that bypass `UserPromptSubmit` (a background task finishing, another
    hook's rewake): the turn this continuation asks about is no longer the latest one.
    """
    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        at = _epoch(entry.get("timestamp"))
        if at is not None and at > armed:
            return True
    return False


def parse_suggestions(text: str) -> Optional[Tuple[str, List[str]]]:
    """`(summary, next_steps)` from the suggester's answer, or None when it has neither."""
    summary, nexts = "", []
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SUMMARY:") and not summary:
            summary = line[len("SUMMARY:"):].strip()
        elif line.upper().startswith("NEXT:") and len(nexts) < MAX_NEXT:
            step = line[len("NEXT:"):].strip()
            if step:
                nexts.append(step[:100])
    if not summary and not nexts:
        return None
    return summary[:600], nexts


def parse_goal(text: str) -> str:
    """The suggester's `GOAL:` line (change relay-continue-original-goal), or ''."""
    for line in (text or "").splitlines():
        line = line.strip()
        if line.upper().startswith("GOAL:"):
            return line[len("GOAL:"):].strip()[:GOAL_MAX]
    return ""


def _own_text(entry: Dict[str, Any]) -> str:
    if entry.get("type") != "user" or entry.get("isMeta"):
        return ""
    content = entry.get("message", {}).get("content") if isinstance(entry.get("message"), dict) else None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return ""
        text = "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    else:
        return ""
    text = text.strip()
    return "" if not text or text.startswith(_NOT_OWN) else text


def opening_prompt(path: Any) -> Optional[str]:
    """The session's first own prompt: why it was started. None when there is none or on any
    read error. Read from the transcript's HEAD, bounded; never logged."""
    if not path:
        return None
    try:
        with open(str(path), encoding="utf-8", errors="replace") as handle:
            for n, line in enumerate(handle):
                if n >= OPENING_HEAD_LINES:
                    break
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    text = _own_text(entry)
                    if text:
                        return text[:OPENING_MAX]
    except OSError as exc:
        logger.debug("continuation: transcript head unreadable: %s", type(exc).__name__)
    return None


def suggest(message: str, get: qr.Getter = local_config.get,
            opening: Optional[str] = None) -> Optional[Tuple[str, List[str], str]]:
    prompt = SUGGEST_PROMPT + message[-wd.MAX_CHARS:]
    if opening:
        prompt += GOAL_PROMPT + opening[:OPENING_MAX]
    out = wd.run_headless(prompt, get, SUGGEST_TIMEOUT_S, label="suggester")
    if out is None:
        return None
    parsed = parse_suggestions(out)
    goal = parse_goal(out)
    if parsed is None and not goal:
        logger.warning("continuation: suggester answer had no SUMMARY/NEXT/GOAL lines (%d chars)", len(out))
        return None
    summary, nexts = parsed if parsed else ("", [])
    return summary, nexts, goal


def continuation_question(project: str, sid: str, summary: str, goal: str = "") -> str:
    head = f"✅ Finished, waiting for the next instruction — {project} · {sid}"
    body = f"\n{summary}" if summary else ""
    if goal:
        ask = (f"\nStarted for: {goal}\nDoes that goal, and the reason the session was started, still hold? "
               f"Keep going, pick a suggestion, or write what it should do next.")
    else:
        ask = ("\nIs anything left of what the session was started for? "
               "Keep going, pick a suggestion, or write what it should do next.")
    return f"{head}{body}{ask}"


def continuation_options(nexts: List[str]) -> List[str]:
    """The fixed keep-going option first, then at most MAX_NEXT suggestions."""
    return [NEXT_MARK + KEEP_GOING] + [NEXT_MARK + n for n in nexts[:MAX_NEXT]]


KEEP_GOING_INSTRUCTION = (
    "Re-read the goal this session was started for and the reason it was started (its opening prompt, "
    "and the handoff if one was loaded). If they still hold and work toward them is left, carry on with "
    "the next step now. If not, say in one line why the goal is met or no longer holds, and stop.")


def instruction(answer: str, by: Optional[str] = None) -> str:
    """The wake text. `by` names a writer other than the operator (B-246): measured
    2026-11-26, an auto-written next step reached two sessions as "The owner answered", and
    one of them built on it as the owner's words. The owner's own wording is unchanged —
    `auto_answer._RELAY_CONTINUE` reads it as an operator quote, and must not read this one."""
    text = answer.strip()
    if text.startswith(NEXT_MARK.strip()):
        text = text[len(NEXT_MARK.strip()):].strip()
    if text == KEEP_GOING:
        text = KEEP_GOING_INSTRUCTION
    if by:
        return ("The auto-answer chose this next step on the owner's behalf, from his standing rules and "
                "earlier answers — the owner did not type it and has not seen it yet. "
                f"Continue with this instruction: {text}")
    return f"The owner answered from the relay channel (they are away from this terminal). Continue with this instruction: {text}"


ENTRYPOINT_ENV = "CLAUDE_CODE_ENTRYPOINT"


def continue_turn(hook_input: Dict[str, Any], *,
                  get: qr.Getter = local_config.get,
                  run: Callable[..., int] = qr._run_command,
                  project_name: Callable[[str], str] = qr._project_name,
                  suggester: Optional[Suggester] = None,
                  clock: Callable[[], float] = time.monotonic,
                  wall: Callable[[], float] = time.time,
                  sleep: Callable[[float], None] = time.sleep,
                  read_entries: Callable[[Any], List[Dict[str, Any]]] = qr.transcript_entries,
                  env: Optional[Dict[str, str]] = None,
                  base: Optional[Path] = None,
                  on_timeout: Optional[Callable[[Dict[str, Any]], Any]] = None) -> Optional[str]:
    """Decide one finished turn. Returns the instruction to wake the session with, or None.

    `on_timeout` gets a carrier job when the relay let the item go ONLY because the hook's
    time ran out (B-250): measured 2026-11-26 21:54, a next step the operator had not seen
    yet dropped off the board after 55 minutes. The hook passes the backfill's carrier.
    """
    env = os.environ if env is None else env
    if env.get(wd.GUARD_ENV):
        return None
    # A headless run (`claude -p`, a timer's check) exits when its turn ends: there is no
    # session to continue, so a "what next?" for it is noise on the operator's channel.
    # Measured 2026-11-24: 8 of 15 continuations relayed that morning were such runs. The
    # runtime tells its children which it is: `cli` interactive, `sdk-cli` for `-p`.
    entry = env.get(ENTRYPOINT_ENV)
    if entry and entry != "cli":
        logger.debug("continuation: headless session (%s=%s); nothing posted", ENTRYPOINT_ENV, entry)
        return None
    state = qr.readiness(get)
    if not (state["enabled"] and state["ready"]) or state["target"] != "command":
        return None
    raw = get(KEY_CONTINUE)
    if raw is not None and not qr._truthy(raw):
        return None
    session_id = str(hook_input.get("session_id") or "")
    sid = qr._safe_id(session_id)[:8]
    if not sid:
        return None
    base = base or qr.state_dir()
    armed = wall()
    turn = wd.turn_key(hook_input)
    transcript = hook_input.get("transcript_path")

    def stale() -> Optional[str]:
        if _superseded_since(session_id, armed, base):
            return "superseded by a prompt typed in the terminal"
        if moved_on(read_entries(transcript), armed):
            return "the session moved on to a newer turn"
        return None

    # The wait detector runs beside this hook at the same Stop; wait for ITS verdict.
    deadline = clock() + VERDICT_WAIT_S
    verdict = None
    while True:
        record = wd.read_verdict(session_id, base)
        if record and record.get("turn") == turn:
            verdict = record.get("verdict")
            break
        if clock() >= deadline:
            logger.info("continuation [%s]: no verdict for this turn within %.0f s; nothing posted", sid, VERDICT_WAIT_S)
            return None
        if stale():
            return None
        sleep(VERDICT_POLL_S)
    if verdict != "DONE":
        logger.debug("continuation [%s]: verdict %s; nothing posted", sid, verdict)
        return None

    message = hook_input.get("last_assistant_message")
    opening = opening_prompt(transcript)
    if suggester is None:
        parsed = suggest(message if isinstance(message, str) else "", get, opening)
    else:
        parsed = suggester(message if isinstance(message, str) else "")
    summary, nexts, goal = "", [], ""
    if parsed:
        summary, nexts = parsed[0], list(parsed[1])
        goal = parsed[2] if len(parsed) > 2 else ""
    project = project_name(str(hook_input.get("cwd") or os.getcwd()))
    if stale():
        logger.info("continuation [%s]: superseded before posting; nothing posted", sid)
        return None
    question = continuation_question(project, sid, summary, goal)
    options = continuation_options(nexts)
    record = qr.hand_over_one(hook_input, qr.KIND_CONTINUATION, question,
                              options, get=get, run=run,
                              project_name=lambda _cwd: project, wall=wall, base=base)
    if record is None:
        return None
    note: Dict[str, Any] = {}
    try:
        answer = qr.wait_one(record, get=get, clock=clock, sleep=sleep, base=base, stale=stale, note=note)
    finally:
        qr.clear_own(record, base)
    if answer is None:
        if note.get("timed_out") and on_timeout is not None:
            job = {"kind": qr.KIND_CONTINUATION, "session_id": session_id,
                   "cwd": str(hook_input.get("cwd") or ""), "project": project,
                   "transcript": transcript, "armed": armed, "started": record.get("started"),
                   "prompt_id": hook_input.get("prompt_id"),
                   "question": question,
                   "options": options}
            try:
                on_timeout(job)
            except Exception as exc:  # the next step stays in the terminal, as before
                logger.warning("continuation [%s]: hand-over after the hook's timeout failed (%s)",
                               sid, type(exc).__name__)
        return None
    logger.info("continuation [%s]: waking the session with the channel answer%s", sid,
                " (written by the auto-answer)" if note.get("by") else "")
    return instruction(answer, note.get("by"))
