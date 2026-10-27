"""Turn an agent's prose wait into a structured question while the question relay is on.

The relay (`question_relay.py`) carries a question asked with `AskUserQuestion`. An agent
that ends its turn waiting in prose — "Then tell me 'done'" — reaches nobody away from the
terminal. This module is the `Stop` hook's decision (`bin/set-hook-wait-detect`):

- relay off, `stop_hook_active`, an empty message, or running inside the classifier's own
  session → nothing (the turn ends as it always did);
- otherwise a small model reads the final message; if the agent is waiting on the user, the
  stop is blocked ONCE with an instruction to ask again with `AskUserQuestion`.

Measured before it was built (real session, 2026-10-11): told to re-ask, the model wrote the
steps into the question and built fitting options itself, and the relay carried it; the
continuation's own Stop carries `stop_hook_active: true`, so this cannot loop.

Everything that fails fails toward today: a missed wait is the status quo, and nothing here
logs the message text.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
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


def classify(message: str, get=local_config.get) -> Optional[str]:
    """`WAITING`, `DONE`, or None when the classifier could not give one of the two."""
    exe = shutil.which("claude")
    if not exe:
        logger.warning("wait detect: no `claude` on PATH; not classified")
        return None
    model = qr._text(get(KEY_MODEL)) or DEFAULT_MODEL
    cmd = [exe, "-p", "--model", model, "--settings", json.dumps({"disableAllHooks": True}),
           "--no-session-persistence"]
    env = {**os.environ, GUARD_ENV: "1"}
    t0 = time.monotonic()
    try:
        res = subprocess.run(cmd, input=PROMPT + message[-MAX_CHARS:], text=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=CLASSIFY_TIMEOUT_S, cwd="/")
    except subprocess.TimeoutExpired:
        logger.warning("wait detect: classifier timed out after %ss", CLASSIFY_TIMEOUT_S)
        return None
    except OSError as exc:
        logger.warning("wait detect: classifier could not start (%s)", type(exc).__name__)
        return None
    took = time.monotonic() - t0
    if res.returncode != 0:
        logger.warning("wait detect: classifier exited %s after %.1fs", res.returncode, took)
        return None
    word = res.stdout.strip().strip(".").upper()
    if word not in ("WAITING", "DONE"):
        logger.warning("wait detect: classifier gave an unexpected answer (%d chars) after %.1fs",
                       len(res.stdout), took)
        return None
    logger.info("wait detect: classified %s in %.1fs", word, took)
    return word


def decide(hook_input: Dict[str, Any], *, get=local_config.get,
           classifier: Optional[Classifier] = None,
           env: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """The Stop hook's output, or None to let the turn end."""
    env = os.environ if env is None else env
    if env.get(GUARD_ENV):
        return None
    if hook_input.get("stop_hook_active"):
        return None
    state = qr.readiness(get)
    if not (state["enabled"] and state["ready"]):
        return None
    message = hook_input.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return None
    sid = qr._safe_id(str(hook_input.get("session_id") or ""))[:8] or "unknown"
    verdict = (classifier or (lambda m: classify(m, get)))(message)
    if verdict != "WAITING":
        return None
    logger.info("wait detect [%s]: the turn ended waiting on the user; asking for a re-ask", sid)
    return {"decision": "block", "reason": REASON}
