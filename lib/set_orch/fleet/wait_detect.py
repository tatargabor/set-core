"""Turn an agent's prose wait into a structured question while the question relay is on.

The relay (`question_relay.py`) carries a question asked with `AskUserQuestion`. An agent
that ends its turn waiting in prose — "Then tell me 'done'" — reaches nobody away from the
terminal. This module is the `Stop` hook's decision (`bin/set-hook-wait-detect`):

- relay off, an empty message, running inside the classifier's own session, or the
  continuation of this detector's own re-ask (`stop_hook_active` after a WAITING verdict)
  → nothing (the turn ends as it always did);
- otherwise a small model reads the final message; if the agent is waiting on the user, the
  stop is blocked ONCE with an instruction to ask again with `AskUserQuestion`.

Measured before it was built (real session, 2026-10-11): told to re-ask, the model wrote the
steps into the question and built fitting options itself, and the relay carried it; the
continuation's own Stop carries `stop_hook_active: true`, so this cannot loop.

Everything that fails fails toward today: a missed wait is the status quo, and nothing here
logs the message text.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .. import local_config
from . import question_relay as qr

logger = logging.getLogger(__name__)

KEY_MODEL = "question_relay.classifier_model"
DEFAULT_MODEL = "haiku"
CLASSIFY_TIMEOUT_S = 25          # inside the hook entry's 60 s
MAX_CHARS = 4000                 # the end of the message is where a wait lives
GUARD_ENV = "SET_WAIT_DETECT_CLASSIFIER"

PROMPT = """You classify the final message an AI coding agent sent before ending its turn.
Answer with exactly one word.

WAITING — the agent cannot usefully continue until the user answers a question, makes a
decision, confirms something, or does something and reports back (e.g. "tell me when done").
DONE — the agent finished or reported, and any closing offer ("tell me if you want more",
"if it still fails, let me know") does not block the work.

MESSAGE:
"""

REASON = (
    "The user is away from this terminal: the question relay is on, so they answer from a chat "
    "channel on their phone. You ended your turn waiting on them. Ask it again now with the "
    "AskUserQuestion tool. Put into the question the context they need to answer without seeing "
    "this terminal (the steps, what to check, what you will do next), and offer short options "
    "that fit — for manual steps, for example 'Done' and 'There was a problem'. They can also "
    "answer in free text."
)

Classifier = Callable[[str], Optional[str]]

#: The verdict a turn got, for the continuation carrier (`continuation.py`): it acts only on
#: DONE, so a WAITING turn is never asked twice. No message text is ever written here.
VERDICTS = ("WAITING", "DONE", "SKIPPED", "UNKNOWN")


def turn_key(hook_input: Dict[str, Any]) -> str:
    """The Stop payload's `prompt_id` (measured present on 2.1.330), else a message hash."""
    pid = qr._safe_id(str(hook_input.get("prompt_id") or ""))
    if pid:
        return pid
    message = hook_input.get("last_assistant_message")
    text = message if isinstance(message, str) else ""
    return "msg-" + hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def verdict_path(session_id: str, base: Optional[Path] = None) -> Path:
    return (base or qr.state_dir()) / "verdicts" / f"{qr._safe_id(session_id)}.json"


def read_verdict(session_id: str, base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The session's latest verdict record, or None when there is none or it is unreadable."""
    path = verdict_path(session_id, base)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("wait detect: verdict record %s unreadable: %s", path.name, type(exc).__name__)
        return None
    return data if isinstance(data, dict) else None


def _record(hook_input: Dict[str, Any], verdict: str, base: Optional[Path]) -> None:
    session_id = str(hook_input.get("session_id") or "")
    if not qr._safe_id(session_id):
        return
    try:
        qr._write_json(verdict_path(session_id, base),
                       {"turn": turn_key(hook_input), "verdict": verdict, "at": time.time()})
    except OSError as exc:  # a missing record only makes the continuation do nothing
        logger.warning("wait detect: verdict record not written: %s", type(exc).__name__)


def run_headless(prompt: str, get=local_config.get, timeout: float = CLASSIFY_TIMEOUT_S,
                 label: str = "classifier") -> Optional[str]:
    """One headless model call: hooks disabled, no session persisted, `cwd=/`, the guard env
    set. Returns stdout, or None on any failure (logged with the outcome and the latency,
    never the text)."""
    exe = shutil.which("claude")
    if not exe:
        logger.warning("wait detect: no `claude` on PATH; %s not run", label)
        return None
    model = qr._text(get(KEY_MODEL)) or DEFAULT_MODEL
    cmd = [exe, "-p", "--model", model, "--settings", json.dumps({"disableAllHooks": True}),
           "--no-session-persistence"]
    env = {**os.environ, GUARD_ENV: "1"}
    t0 = time.monotonic()
    try:
        res = subprocess.run(cmd, input=prompt, text=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=timeout, cwd="/")
    except subprocess.TimeoutExpired:
        logger.warning("wait detect: %s timed out after %ss", label, timeout)
        return None
    except OSError as exc:
        logger.warning("wait detect: %s could not start (%s)", label, type(exc).__name__)
        return None
    took = time.monotonic() - t0
    if res.returncode != 0:
        logger.warning("wait detect: %s exited %s after %.1fs", label, res.returncode, took)
        return None
    logger.debug("wait detect: %s answered in %.1fs", label, took)
    return res.stdout


def classify(message: str, get=local_config.get) -> Optional[str]:
    """`WAITING`, `DONE`, or None when the classifier could not give one of the two."""
    t0 = time.monotonic()
    out = run_headless(PROMPT + message[-MAX_CHARS:], get, CLASSIFY_TIMEOUT_S)
    if out is None:
        return None
    took = time.monotonic() - t0
    word = out.strip().strip(".").upper()
    if word not in ("WAITING", "DONE"):
        logger.warning("wait detect: classifier gave an unexpected answer (%d chars) after %.1fs",
                       len(out), took)
        return None
    logger.info("wait detect: classified %s in %.1fs", word, took)
    return word


def decide(hook_input: Dict[str, Any], *, get=local_config.get,
           classifier: Optional[Classifier] = None,
           env: Optional[Dict[str, str]] = None,
           base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The Stop hook's output, or None to let the turn end.

    Every turn decided while the relay is on leaves a verdict record (no text). A turn with
    `stop_hook_active` is skipped only when it continues this detector's OWN re-ask (the
    previous verdict is WAITING) — that is the loop guard. A turn woken by the continuation
    carrier also ends with `stop_hook_active: true` (measured 2026-11-22), and skipping it
    would make a channel-continued session invisible after its first continuation.
    """
    env = os.environ if env is None else env
    if env.get(GUARD_ENV):
        return None
    state = qr.readiness(get)
    if not (state["enabled"] and state["ready"]):
        return None
    session_id = str(hook_input.get("session_id") or "")
    sid = qr._safe_id(session_id)[:8] or "unknown"
    if hook_input.get("stop_hook_active"):
        previous = read_verdict(session_id, base)
        if previous is None or previous.get("verdict") == "WAITING":
            # No record = nothing proves this is not our own continuation: keep the guard.
            _record(hook_input, "SKIPPED", base)
            return None
    message = hook_input.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        _record(hook_input, "SKIPPED", base)
        return None
    verdict = (classifier or (lambda m: classify(m, get)))(message)
    _record(hook_input, verdict if verdict in VERDICTS else "UNKNOWN", base)
    if verdict != "WAITING":
        return None
    logger.info("wait detect [%s]: the turn ended waiting on the user; asking for a re-ask", sid)
    return {"decision": "block", "reason": REASON}
