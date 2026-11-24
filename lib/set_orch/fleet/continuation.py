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
Give zero to three NEXT lines; none when nothing sensible follows.

MESSAGE:
"""

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


def suggest(message: str, get: qr.Getter = local_config.get) -> Optional[Tuple[str, List[str]]]:
    out = wd.run_headless(SUGGEST_PROMPT + message[-wd.MAX_CHARS:], get, SUGGEST_TIMEOUT_S, label="suggester")
    if out is None:
        return None
    parsed = parse_suggestions(out)
    if parsed is None:
        logger.warning("continuation: suggester answer had no SUMMARY/NEXT lines (%d chars)", len(out))
    return parsed


def continuation_question(project: str, sid: str, summary: str) -> str:
    head = f"✅ Finished, waiting for the next instruction — {project} · {sid}"
    body = f"\n{summary}" if summary else ""
    return f"{head}{body}\nPick a suggestion or write what it should do next; the session continues with it."


def instruction(answer: str) -> str:
    text = answer.strip()
    if text.startswith(NEXT_MARK.strip()):
        text = text[len(NEXT_MARK.strip()):].strip()
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
                  base: Optional[Path] = None) -> Optional[str]:
    """Decide one finished turn. Returns the instruction to wake the session with, or None."""
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
    parsed = (suggester or (lambda m: suggest(m, get)))(message if isinstance(message, str) else "")
    summary, nexts = parsed if parsed else ("", [])
    project = project_name(str(hook_input.get("cwd") or os.getcwd()))
    if stale():
        logger.info("continuation [%s]: superseded before posting; nothing posted", sid)
        return None
    record = qr.hand_over_one(hook_input, qr.KIND_CONTINUATION, continuation_question(project, sid, summary),
                              [NEXT_MARK + n for n in nexts], get=get, run=run,
                              project_name=lambda _cwd: project, wall=wall, base=base)
    if record is None:
        return None
    try:
        answer = qr.wait_one(record, get=get, clock=clock, sleep=sleep, base=base, stale=stale)
    finally:
        qr.clear_own(record, base)
    if answer is None:
        return None
    logger.info("continuation [%s]: waking the session with the channel answer", sid)
    return instruction(answer)
