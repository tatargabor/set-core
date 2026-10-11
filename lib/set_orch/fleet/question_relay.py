"""Relay an interactive agent's blocking question to a chat channel, and the answer back.

The carrier is a `PreToolUse` hook on `AskUserQuestion` (`bin/set-hook-question-relay`).
Measured on the runtime before this was built (2026-10-10/11, interactive sessions):

- the hook can ANSWER the question: `permissionDecision: "allow"` plus the original input
  with `answers` added, and no picker appears; a hook waited 700 s and still delivered;
- a hook that exits 0 with NO output RELEASES it: the normal picker appears, and the
  question is then in the transcript like any other;
- while the hook waits, the session reads as busy and the question is not in the
  transcript — so this module keeps a waiting record, or the fleet could not see it.

Three rules shape everything below, and each is a rule, not a taste:

- **Fail-open to the terminal.** Every failure releases. The relay never answers with a
  default, and a question it has released it never answers afterwards.
- **The framework never completes a configuration by guess.** The outbound, its command or
  URL, and the audience come from this machine's local config; a missing key is reported by
  name and the question is released.
- **No question text in anything this module persists or logs.** The waiting record holds
  counts and identities; the text stays in the transcript and with the outbound.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import local_config

logger = logging.getLogger(__name__)

TARGETS = ("command", "webhook")
DEFAULT_TIMEOUT_S = 3300          # below the hook entry's own 3600 s, so this fires first
POLL_S = 3.0
ANSWER_RETENTION_S = 7 * 24 * 3600
TOOL = "AskUserQuestion"

KEY_ENABLED = "question_relay.enabled"
KEY_TARGET = "question_relay.target"
KEY_COMMAND = "question_relay.command"
KEY_AUDIENCE = "question_relay.audience"
KEY_WEBHOOK = "question_relay.webhook_url"
KEY_DETAIL = "question_relay.webhook_detail"
KEY_TIMEOUT = "question_relay.timeout_s"

#: What each target cannot work without. The framework supplies none of these.
REQUIRED = {
    "command": (KEY_COMMAND, KEY_AUDIENCE),
    "webhook": (KEY_WEBHOOK,),
}

Getter = Callable[..., Any]


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def readiness(get: Getter = local_config.get) -> Dict[str, Any]:
    """Whether the relay is on, which outbound it uses, and what is missing.

    The hook and the fleet both call this, so the screen's "not ready" and the hook's
    release are one decision, not two copies of it.
    """
    target = _text(get(KEY_TARGET))
    missing: List[str] = []
    if target not in TARGETS:
        missing.append(KEY_TARGET)
    else:
        missing.extend(k for k in REQUIRED[target] if not _text(get(k)))
    return {
        "enabled": _truthy(get(KEY_ENABLED, default=False)),
        "target": target or None,
        "missing": missing,
        "ready": not missing,
    }


def set_enabled(enabled: bool, get: Getter = local_config.get) -> Dict[str, Any]:
    """Turn the relay on or off. Turning it on is refused while the configuration is incomplete."""
    state = readiness(get)
    if enabled and not state["ready"]:
        raise ValueError("not ready: missing " + ", ".join(state["missing"]))
    local_config.set_value(KEY_ENABLED, bool(enabled))
    return readiness(get)


def timeout_s(get: Getter = local_config.get) -> float:
    try:
        value = float(get(KEY_TIMEOUT, default=DEFAULT_TIMEOUT_S))
    except (TypeError, ValueError):
        logger.warning("question relay: %s is not a number; using %s", KEY_TIMEOUT, DEFAULT_TIMEOUT_S)
        return float(DEFAULT_TIMEOUT_S)
    return max(1.0, min(value, float(DEFAULT_TIMEOUT_S)))


# --------------------------------------------------------------------------- #
# state directory
# --------------------------------------------------------------------------- #

def state_dir() -> Path:
    override = os.environ.get("SET_QUESTION_RELAY_DIR")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "set-core" / "question-relay"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]", "", value or "")


def waiting_path(session_id: str, base: Optional[Path] = None) -> Path:
    return (base or state_dir()) / "waiting" / f"{_safe_id(session_id)}.json"


def release_path(session_id: str, base: Optional[Path] = None) -> Path:
    return (base or state_dir()) / "waiting" / f"{_safe_id(session_id)}.release"


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _hook_alive(pid: Any) -> bool:
    """Whether the hook process that wrote a record still runs.

    B-159: the hook clears its record in a `finally:`, which a killed process never reaches
    (the session interrupted or closed), so a record can outlive its wait. A record without
    a pid predates the fix and is trusted as before.
    """
    if not isinstance(pid, int) or pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return True          # no /proc (macOS): the pid alone answers
    return b"question-relay" in cmdline or b"question_relay" in cmdline


def list_waiting(base: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every question waiting on a two-way outbound. A broken record is skipped and logged;
    a record whose hook process is gone is removed (B-159)."""
    folder = (base or state_dir()) / "waiting"
    out: List[Dict[str, Any]] = []
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("question relay: waiting record %s unreadable: %s", path.name, type(exc).__name__)
            continue
        if isinstance(record, dict) and not _hook_alive(record.get("pid")):
            logger.warning("question relay: waiting record %s has no live hook (pid %s); removed",
                           path.name, record.get("pid"))
            _clear_waiting(str(record.get("session_id", path.stem)), base or state_dir())
            continue
        if isinstance(record, dict):
            record["release_requested"] = release_path(record.get("session_id", ""), base).exists()
            out.append(record)
    return out


def request_release(session_id: str, base: Optional[Path] = None) -> bool:
    """Ask the waiting hook of this session to hand its question back to the terminal."""
    if not waiting_path(session_id, base).exists():
        return False
    path = release_path(session_id, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()), encoding="utf-8")
    logger.info("question relay: release requested for session %s", _safe_id(session_id)[:8])
    return True


def _clear_waiting(session_id: str, base: Path) -> None:
    for path in (waiting_path(session_id, base), release_path(session_id, base)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("question relay: could not remove %s: %s", path.name, type(exc).__name__)


def prune_answers(base: Path, now: float) -> int:
    """Answers that arrived for released questions are never read; drop them after a week."""
    folder = base / "answers"
    removed = 0
    if not folder.is_dir():
        return 0
    for path in folder.glob("*.json"):
        try:
            if now - path.stat().st_mtime > ANSWER_RETENTION_S:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("question relay: pruned %d stale answer file(s)", removed)
    return removed


# --------------------------------------------------------------------------- #
# the envelope and the answer
# --------------------------------------------------------------------------- #

def call_id(session_id: str, tool_use_id: str) -> str:
    """One id per tool call: `relay-<session 8>-<hash 8>`. Safe in a file name and a chat post."""
    digest = hashlib.sha256(f"{session_id}:{tool_use_id}".encode()).hexdigest()[:8]
    return f"relay-{_safe_id(session_id)[:8]}-{digest}"


def questions_of(tool_input: Dict[str, Any]) -> List[Dict[str, Any]]:
    qs = tool_input.get("questions") if isinstance(tool_input, dict) else None
    return [q for q in qs if isinstance(q, dict)] if isinstance(qs, list) else []


def build_envelope(tool_input: Dict[str, Any], cid: str, audience: str, source: str,
                   answer_dir: Path) -> Dict[str, Any]:
    """The question list in the shape the existing chat bridge speaks (field names verbatim)."""
    entries = []
    for i, q in enumerate(questions_of(tool_input), start=1):
        options = [str(o.get("label", "")) for o in q.get("options", []) if isinstance(o, dict)]
        entries.append({
            "id": cid,
            "key": f"Q{i}",
            "question": str(q.get("question", "")),
            "optionsList": [o for o in options if o],
            "multi": bool(q.get("multiSelect", False)),
            "audience": audience,
            "source": source,
            "valasz_tar": str(answer_dir),
        })
    return {"questions": entries}


def answer_file(answer_dir: Path, cid: str, key: str) -> Path:
    # The bridge names the file from `<id>#<key>` with `#` → `__`; the id is already safe.
    return answer_dir / f"{cid}__{key}.json"


def collect_answers(answer_dir: Path, cid: str, count: int) -> List[Optional[str]]:
    """Each question's answer text, or None where it has not arrived (or is unreadable/empty)."""
    out: List[Optional[str]] = []
    for i in range(1, count + 1):
        path = answer_file(answer_dir, cid, f"Q{i}")
        text: Optional[str] = None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                value = data.get("valasz") if isinstance(data, dict) else None
                if isinstance(value, str) and value.strip():
                    text = value.strip()
            except (OSError, ValueError) as exc:
                logger.warning("question relay: answer %s unreadable: %s", path.name, type(exc).__name__)
        out.append(text)
    return out


def answer_output(tool_input: Dict[str, Any], texts: List[str]) -> Dict[str, Any]:
    """The hook result that answers the tool call: allow, with `answers` added to the input."""
    answers = {str(q.get("question", "")): t for q, t in zip(questions_of(tool_input), texts)}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {**tool_input, "answers": answers},
        }
    }


# --------------------------------------------------------------------------- #
# the webhook
# --------------------------------------------------------------------------- #

def webhook_message(project: str, session_id: str, tool_input: Dict[str, Any], detail: str) -> str:
    qs = questions_of(tool_input)
    head = f"❓ An agent is waiting for an answer — {project} · {_safe_id(session_id)[:8]}"
    lines = [head]
    for q in qs:
        header = str(q.get("header", "")).strip() or "question"
        if detail == "full":
            lines.append(f"• **{header}** — {q.get('question', '')}")
            for o in q.get("options", []):
                if isinstance(o, dict) and o.get("label"):
                    lines.append(f"    – {o['label']}")
        else:
            lines.append(f"• {header}")
    lines.append("Answer it at the agent's terminal or in the fleet.")
    return "\n".join(lines)[:1900]


def post_webhook(url: str, content: str, timeout: float = 10.0) -> None:
    body = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "set-core-question-relay"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - operator-configured URL
        resp.read()


# --------------------------------------------------------------------------- #
# the decision loop
# --------------------------------------------------------------------------- #

def _project_name(cwd: str) -> str:
    try:
        from ..paths import resolve_project_name
        return resolve_project_name(cwd)
    except Exception as exc:  # a project name is a label; never let it stop the relay
        logger.debug("question relay: project name unresolved: %s", type(exc).__name__)
        return os.path.basename(cwd.rstrip("/")) or "unknown"


def _run_command(command: str, payload: str) -> int:
    # No output pipe is held, on purpose. With a pipe, `run` waits until EVERY holder of
    # it has closed it — and a bridge that leaves a background child running (a poller, a
    # delayed sender) keeps it open, so the hand-off itself blocks and nothing waits in
    # the record the fleet reads. Measured on the first live run: "handed over" and
    # "answered" logged in the same millisecond, after the child had finished. The
    # bridge's own output is its own log's business; the exit code is what decides here.
    return subprocess.run(shlex.split(command), input=payload, text=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=120).returncode


def relay(hook_input: Dict[str, Any], *,
          get: Getter = local_config.get,
          run: Callable[[str, str], int] = _run_command,
          post: Callable[[str, str], None] = post_webhook,
          project_name: Callable[[str], str] = _project_name,
          clock: Callable[[], float] = time.monotonic,
          wall: Callable[[], float] = time.time,
          sleep: Callable[[float], None] = time.sleep,
          base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Decide one `AskUserQuestion` call. Returns the hook output to print, or None to release."""
    if hook_input.get("tool_name") != TOOL:
        return None
    state = readiness(get)
    if not state["enabled"]:
        return None
    session_id = str(hook_input.get("session_id") or "")
    sid = _safe_id(session_id)[:8] or "unknown"
    tool_input = hook_input.get("tool_input") or {}
    count = len(questions_of(tool_input))
    if count == 0:
        logger.warning("question relay [%s]: no questions in the call; released", sid)
        return None
    if not state["ready"]:
        logger.warning("question relay [%s]: not ready, missing %s; released", sid, ", ".join(state["missing"]))
        return None

    cwd = str(hook_input.get("cwd") or os.getcwd())
    project = project_name(cwd)
    base = base or state_dir()

    if state["target"] == "webhook":
        detail = "full" if _text(get(KEY_DETAIL)) == "full" else "minimal"
        try:
            post(_text(get(KEY_WEBHOOK)), webhook_message(project, session_id, tool_input, detail))
            logger.info("question relay [%s]: webhook notified (%d question(s), %s); released", sid, count, detail)
        except Exception as exc:
            logger.warning("question relay [%s]: webhook post failed (%s); released", sid, type(exc).__name__)
        return None

    # target == "command": hand over, then wait.
    answer_dir = base / "answers"
    answer_dir.mkdir(parents=True, exist_ok=True)
    prune_answers(base, wall())
    cid = call_id(session_id, str(hook_input.get("tool_use_id") or wall()))
    envelope = build_envelope(tool_input, cid, _text(get(KEY_AUDIENCE)), f"{project} · {sid}", answer_dir)
    try:
        code = run(_text(get(KEY_COMMAND)), json.dumps(envelope, ensure_ascii=False))
    except Exception as exc:
        logger.warning("question relay [%s]: outbound could not run (%s); released", sid, type(exc).__name__)
        return None
    if code != 0:
        logger.warning("question relay [%s]: outbound exited %s; released", sid, code)
        return None

    _clear_waiting(session_id, base)
    _write_json(waiting_path(session_id, base), {
        "session_id": session_id, "id": cid, "project": project, "cwd": cwd,
        "questions": count, "target": "command", "started": wall(), "pid": os.getpid(),
    })
    logger.info("question relay [%s]: %d question(s) handed over as %s; waiting", sid, count, cid)

    deadline = clock() + timeout_s(get)
    try:
        while True:
            texts = collect_answers(answer_dir, cid, count)
            if all(t is not None for t in texts):
                logger.info("question relay [%s]: answered on the channel (%s)", sid, cid)
                for i in range(1, count + 1):
                    answer_file(answer_dir, cid, f"Q{i}").unlink(missing_ok=True)
                return answer_output(tool_input, [t for t in texts if t is not None])
            if not readiness(get)["enabled"]:
                logger.info("question relay [%s]: switch turned off while waiting; released", sid)
                return None
            if release_path(session_id, base).exists():
                logger.info("question relay [%s]: released from the fleet", sid)
                return None
            if clock() >= deadline:
                logger.warning("question relay [%s]: no answer within %.0f s; released", sid, timeout_s(get))
                return None
            sleep(POLL_S)
    finally:
        _clear_waiting(session_id, base)
