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
import inspect
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
#: One-way notification of the blocking messages that are not questions (B-184): a
#: permission prompt or a waiting-for-input notice cannot be answered through the
#: channel, so it takes its own outbound — a command that posts, or the webhook.
KEY_NOTIFY_COMMAND = "question_relay.notify_command"

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
    # The notify outbound is a separate gate on purpose: a machine that relays questions
    # but has not configured notifications must not lose the questions — it gets its own
    # named gap, which readiness surfaces without touching `ready` for questions.
    notify_missing: List[str] = []
    if _truthy(get(KEY_ENABLED, default=False)) and not (_text(get(KEY_NOTIFY_COMMAND)) or _text(get(KEY_WEBHOOK))):
        notify_missing.append(KEY_NOTIFY_COMMAND)
    return {
        "enabled": _truthy(get(KEY_ENABLED, default=False)),
        "target": target or None,
        "missing": missing,
        "ready": not missing,
        "notify_missing": notify_missing,
    }


RELAY_HOOK = "set-hook-question-relay"
WAIT_HOOK = "set-hook-wait-detect"
NOTIFY_HOOK = "set-hook-notify-relay"
PERMISSION_HOOK = "set-hook-permission-relay"
CONTINUE_HOOK = "set-hook-continue-relay"
SUPERSEDE_HOOK = "set-hook-relay-supersede"
#: Every hook the relay needs in a project, in the order the unwired list names them.
ALL_HOOKS = (RELAY_HOOK, WAIT_HOOK, NOTIFY_HOOK, PERMISSION_HOOK, CONTINUE_HOOK, SUPERSEDE_HOOK)
#: A PreToolUse matcher that covers AskUserQuestion: the tool's own name, or a match-all.
_ASK_MATCHERS = (TOOL, "", "*", None)


def _hooks_in(settings: Any) -> set:
    """Which of the relay hooks one settings document wires (B-182)."""
    found: set = set()
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks, dict):
        return found
    for entry in hooks.get("PreToolUse") or []:
        if not isinstance(entry, dict) or entry.get("matcher") not in _ASK_MATCHERS:
            continue
        if any(isinstance(h, dict) and h.get("command") == RELAY_HOOK for h in entry.get("hooks") or []):
            found.add(RELAY_HOOK)
    for entry in hooks.get("Stop") or []:
        if not isinstance(entry, dict):
            continue
        if any(isinstance(h, dict) and h.get("command") == WAIT_HOOK for h in entry.get("hooks") or []):
            found.add(WAIT_HOOK)
    for event, name in (("Notification", NOTIFY_HOOK), ("PermissionRequest", PERMISSION_HOOK),
                        ("UserPromptSubmit", SUPERSEDE_HOOK)):
        for entry in hooks.get(event) or []:
            if not isinstance(entry, dict):
                continue
            if any(isinstance(h, dict) and h.get("command") == name for h in entry.get("hooks") or []):
                found.add(name)
    for entry in hooks.get("Stop") or []:
        if not isinstance(entry, dict):
            continue
        # Only the ASYNC entry counts: run synchronously it would hold the idle session
        # for the whole wait, which is exactly what it must never do.
        if any(isinstance(h, dict) and h.get("command") == CONTINUE_HOOK and h.get("asyncRewake") is True
               for h in entry.get("hooks") or []):
            found.add(CONTINUE_HOOK)
    return found


def _settings_hooks(path: Path) -> set:
    try:
        return _hooks_in(json.loads(path.read_text()))
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as exc:
        # Unreadable counts as unwired: a hook the runtime cannot parse does not run either.
        logger.warning("question relay: settings %s unreadable: %s", path, type(exc).__name__)
        return set()


def unwired_projects(projects: Optional[List[Dict[str, Any]]] = None,
                     user_settings: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Registered projects whose sessions would bypass the relay — B-182.

    `readiness()` measures this machine's config; it cannot see that a project's own
    settings never wired the hook, so a question asked there stays in its terminal while
    the switch says ready. Measured 2026-11-17: 47 of 48 registered projects wired both
    hooks, the one that did not keeps a hand-authored hook chain, and its question was
    shown only in the terminal. A hook in the user-level settings covers every project.
    """
    if projects is None:
        from ..project_registry import load_projects
        projects = load_projects()
    user = _settings_hooks(user_settings or (Path.home() / ".claude" / "settings.json"))
    out: List[Dict[str, Any]] = []
    for proj in projects:
        if not isinstance(proj, dict) or proj.get("archived"):
            continue
        root = Path(str(proj.get("path") or ""))
        if not str(proj.get("path") or "") or not root.is_dir():
            continue
        found = set(user)
        found |= _settings_hooks(root / ".claude" / "settings.json")
        found |= _settings_hooks(root / ".claude" / "settings.local.json")
        missing = [h for h in ALL_HOOKS if h not in found]
        if missing:
            out.append({"project": proj.get("name") or root.name, "missing": missing})
    return out


_RELAY_ENTRY = {"matcher": TOOL, "hooks": [{"type": "command", "command": RELAY_HOOK, "timeout": 3600}]}
_WAIT_ENTRY = {"matcher": "", "hooks": [{"type": "command", "command": WAIT_HOOK, "timeout": 60}]}
_NOTIFY_ENTRY = {"matcher": "", "hooks": [{"type": "command", "command": NOTIFY_HOOK, "timeout": 30}]}
# Above the relay's own 3300 s wait, so the carrier's release always fires first.
_PERMISSION_ENTRY = {"matcher": "", "hooks": [{"type": "command", "command": PERMISSION_HOOK, "timeout": 3700}]}
_CONTINUE_ENTRY = {"matcher": "", "hooks": [{"type": "command", "command": CONTINUE_HOOK, "timeout": 3700,
                                             "asyncRewake": True}]}
_SUPERSEDE_ENTRY = {"matcher": "", "hooks": [{"type": "command", "command": SUPERSEDE_HOOK, "timeout": 5}]}


def _exclude_from_git(root: Path, rel: str) -> None:
    """Keep a machine-local file out of git without touching a tracked file.

    `.git/info/exclude` is per-clone and never committed, so the repository's own
    `.gitignore` — which belongs to its owner — stays as it was.
    """
    try:
        probe = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", rel],
                               capture_output=True, timeout=10)
        if probe.returncode == 0:
            return
        gitdir = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                                capture_output=True, text=True, timeout=10)
        if gitdir.returncode != 0:
            return  # not a repository: nothing can commit the file
        info = Path(gitdir.stdout.strip())
        if not info.is_absolute():
            info = root / info
        exclude = info / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text() if exclude.exists() else ""
        if rel not in text.splitlines():
            exclude.write_text(text + ("" if text.endswith("\n") or not text else "\n") + rel + "\n")
            logger.info("question relay: %s excluded from git in %s", rel, root)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("question relay: could not exclude %s in %s: %s", rel, root, type(exc).__name__)


def wire_project(root: Path, user_settings: Optional[Path] = None) -> List[str]:
    """Wire whatever relay hook a project lacks into its MACHINE-LOCAL settings.

    Returns the hooks added (empty when nothing was missing). Writes only
    `.claude/settings.local.json`, merging into what is there: the project's own
    `settings.json` is its owner's, a project registered without deploy must not get
    tracked set-core files, and the relay switch itself is machine-local config. A hook
    already wired at any level is never added twice — two relay hooks would post every
    question twice.
    """
    root = Path(root)
    found = _settings_hooks(user_settings or (Path.home() / ".claude" / "settings.json"))
    found |= _settings_hooks(root / ".claude" / "settings.json")
    local = root / ".claude" / "settings.local.json"
    found |= _settings_hooks(local)
    missing = [h for h in ALL_HOOKS if h not in found]
    if not missing:
        return []
    data: Dict[str, Any] = {}
    if local.exists():
        try:
            data = json.loads(local.read_text())
        except (OSError, ValueError) as exc:
            # Never overwrite a file we cannot read: that would destroy its owner's content.
            logger.warning("question relay: %s unreadable (%s); not wired", local, type(exc).__name__)
            raise
        if not isinstance(data, dict):
            raise ValueError(f"{local} is not a JSON object")
    hooks = data.setdefault("hooks", {})
    if RELAY_HOOK in missing:
        hooks.setdefault("PreToolUse", []).append(json.loads(json.dumps(_RELAY_ENTRY)))
    if WAIT_HOOK in missing:
        hooks.setdefault("Stop", []).append(json.loads(json.dumps(_WAIT_ENTRY)))
    for name, event, entry in ((NOTIFY_HOOK, "Notification", _NOTIFY_ENTRY),
                               (PERMISSION_HOOK, "PermissionRequest", _PERMISSION_ENTRY),
                               (CONTINUE_HOOK, "Stop", _CONTINUE_ENTRY),
                               (SUPERSEDE_HOOK, "UserPromptSubmit", _SUPERSEDE_ENTRY)):
        if name in missing:
            hooks.setdefault(event, []).append(json.loads(json.dumps(entry)))
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, local)
    _exclude_from_git(root, ".claude/settings.local.json")
    logger.info("question relay: wired %s into %s", ", ".join(missing), local)
    return missing


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


#: What a live relay carrier's command line contains. A carrier missing here has its record
#: read as orphaned and removed — which the bridge takes as a release and closes the post
#: mid-wait. B-192: a list of carrier NAMES is a copy held by a different, long-lived
#: process (set-web), so a reader started before a new carrier shipped deleted every one of
#: its records. The shared `set-hook-` prefix covers any carrier, present or future; the
#: check only guards against a reused pid, which a `set-hook-` process almost never is.
#: `relay-backfill` is the carrier of a question pulled in at switch-on (fleet-relay-backfill),
#: which runs as `set-relay-backfill --carry`, or as the module when the script is missing.
_CARRIER_MARKS = (b"set-hook-", b"question-relay", b"question_relay", b"relay-backfill", b"relay_backfill")


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
    return any(name in cmdline for name in _CARRIER_MARKS)


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


SESSION_RECORDS = Path.home() / ".claude" / "sessions"


def release_on_terminal_enter(agent_pid: int, base: Optional[Path] = None,
                              records: Path = SESSION_RECORDS) -> Optional[str]:
    """The operator pressed Enter in the asking agent's terminal: hand its held question back.

    B-214, measured 2026-11-24: a relayed AskUserQuestion holds the turn inside the hook, so
    a message typed in the terminal only QUEUES behind it ("Queued · ctrl+x ctrl+s") and the
    agent sat for 16 min until the fleet's "answer here instead". A person typing into that
    terminal is at the machine, which is the same fact that button states. A continuation is
    left alone — there the turn has ended and the typed prompt already supersedes it.
    Returns the released session id, or None.
    """
    try:
        data = json.loads((records / f"{int(agent_pid)}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    session_id = str(data.get("sessionId") or "") if isinstance(data, dict) else ""
    if not session_id:
        return None
    record = waiting_record(session_id, base)
    if not record or record.get("release_requested") or record.get("kind") == "continuation":
        return None
    if release_path(session_id, base).exists():
        return None
    if request_release(session_id, base):
        logger.info("question relay [%s]: Enter typed in its terminal; question handed back there",
                    _safe_id(session_id)[:8])
        return session_id
    return None


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


def waiting_record(session_id: str, base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The live waiting record for one session, or None."""
    for record in list_waiting(base):
        if record.get("session_id") == session_id:
            return record
    return None


def deliver_answer(session_id: str, text: str, base: Optional[Path] = None) -> Optional[str]:
    """Answer a waiting single-question call through the relay's own answer store.

    The same file the chat bridge writes (`answers/<id>__Q1.json`, `{"valasz": …}`): the
    waiting hook reads it within one poll, answers the tool call and deletes the file.
    Returns None on success, else the reason it could not be delivered. A call with more
    than one question is refused — one text cannot answer several questions honestly.
    """
    record = waiting_record(session_id, base)
    if record is None:
        return "no relayed question is waiting for that agent"
    if record.get("release_requested"):
        return "the question was already handed back to the terminal"
    if int(record.get("questions") or 0) != 1:
        return "the agent asked several questions at once; answer them in its terminal"
    cid = str(record.get("id") or "")
    if not cid or not text.strip():
        return "nothing to deliver"
    answer_dir = (base or state_dir()) / "answers"
    _write_json(answer_file(answer_dir, cid, "Q1"), {"valasz": text.strip()})
    logger.info("question relay [%s]: answer handed over from the fleet (%s)",
                _safe_id(session_id)[:8], cid)
    return None


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

def _repo_root_by_walk(cwd: str) -> Optional[str]:
    """The nearest ancestor holding `.git` (a directory, or a worktree's file) — no subprocess."""
    p = Path(cwd).resolve() if cwd else None
    while p is not None:
        if (p / ".git").exists():
            return str(p)
        p = p.parent if p.parent != p else None
    return None


def _project_name(cwd: str) -> str:
    try:
        from ..paths import resolve_project_name
        name = resolve_project_name(cwd)
        if name and name != "_global":
            return name
    except Exception as exc:  # a project name is a label; never let it stop the relay
        # Measured 2026-11-24: in a Stop hook this raised and the fallback named a session
        # after its CURRENT directory ("lib") — logged at debug, so nobody saw why.
        logger.warning("question relay: project name unresolved (%s); walking up for .git", type(exc).__name__)
    root = _repo_root_by_walk(cwd)
    return os.path.basename(root) if root else (os.path.basename(cwd.rstrip("/")) or "unknown")


#: What the relay tells its outbound about the call, beside the envelope (fleet-auto-answer
#: D3). The envelope is what a chat bridge posts verbatim, so a local path or a session id
#: in it would reach a channel; the environment reaches only the outbound process.
ENV_KIND = "SET_RELAY_KIND"
ENV_SESSION = "SET_RELAY_SESSION"
ENV_CWD = "SET_RELAY_CWD"
KIND_ASK = "ask"


def relay_env(kind: str, session_id: str, cwd: str) -> Dict[str, str]:
    """The three variables the outbound receives: which blocking point, whose, where."""
    return {ENV_KIND: kind, ENV_SESSION: session_id, ENV_CWD: cwd}


def _takes_env(run: Callable[..., int]) -> bool:
    try:
        return "env" in inspect.signature(run).parameters
    except (TypeError, ValueError):
        return False


def _hand(run: Callable[..., int], command: str, payload: str, env: Dict[str, str]) -> int:
    """Run the outbound, with the call's environment when the runner can take it.

    A runner injected without an `env` parameter (an older test double, a caller's own
    runner) is called exactly as before, so the hand-over contract stays two-argument.
    """
    if _takes_env(run):
        return run(command, payload, env=env)
    return run(command, payload)


def _run_command(command: str, payload: str, env: Optional[Dict[str, str]] = None) -> int:
    # No output pipe is held, on purpose. With a pipe, `run` waits until EVERY holder of
    # it has closed it — and a bridge that leaves a background child running (a poller, a
    # delayed sender) keeps it open, so the hand-off itself blocks and nothing waits in
    # the record the fleet reads. Measured on the first live run: "handed over" and
    # "answered" logged in the same millisecond, after the child had finished. The
    # bridge's own output is its own log's business; the exit code is what decides here.
    return subprocess.run(shlex.split(command), input=payload, text=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          env={**os.environ, **env} if env else None,
                          timeout=120).returncode


# --------------------------------------------------------------------------- #
# notifications: the blocking messages that are not questions (B-184)
# --------------------------------------------------------------------------- #

NOTIFY_TIMEOUT_S = 25


def _run_notify(command: str, payload: str) -> int:
    # The same no-pipe rule as _run_command (a bridge that leaves a child running must
    # not hold the hand-off open); the shorter timeout is the point — a notification
    # must never hold a hook slot the way a held question may.
    return subprocess.run(shlex.split(command), input=payload, text=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=NOTIFY_TIMEOUT_S).returncode


def _tool_summary(block: Dict[str, Any]) -> str:
    """One line naming what is actually being asked, or '' when it says nothing."""
    name = str(block.get("name") or "")
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    if name == "Bash":
        command = _text(inp.get("command")).replace("\n", " ; ")
        return f"Bash: {command[:160]}" if command else ""
    if name in ("Edit", "Write", "Read", "NotebookEdit"):
        target = _text(inp.get("file_path"))
        return f"{name}: {target[:120]}" if target else ""
    if name == TOOL:
        return ""  # a question tool's ask is the OTHER carrier's job — never double-report
    return name


def enrich_message(hook_input: Dict[str, Any]) -> str:
    """The runtime's notification text plus WHAT is being asked, from the transcript.

    The notification event itself carries only a generic sentence ("Claude needs your
    permission to use Bash"), measured 2026-11-19 as 32 characters on a real prompt —
    the owner cannot act on that from the channel. The transcript's most recent
    tool_use is the thing the prompt is about; its summary is appended. Best effort:
    any unreadable transcript returns the message unchanged, and a newest tool_use
    that is a question tool returns the message unchanged too (the question relay
    owns that ask, and an older tool_use is not the pending one).
    """
    message = _text(hook_input.get("message"))
    path = hook_input.get("transcript_path")
    if not path:
        return message
    try:
        with open(str(path), "rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            tail = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        logger.debug("question relay notify: transcript unreadable: %s", type(exc).__name__)
        return message
    for line in reversed([ln for ln in tail.split("\n") if ln.strip()]):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = entry.get("message", {}).get("content") if isinstance(entry, dict) else None
        if not isinstance(content, list):
            continue
        newest = next((b for b in reversed(content)
                       if isinstance(b, dict) and b.get("type") == "tool_use"), None)
        if newest is None:
            continue
        if newest.get("name") == TOOL:
            return message
        summary = _tool_summary(newest)
        if summary and summary not in message:
            return f"{message} — {summary}" if message else summary
        return message
    return message


#: A notification for a session whose blocking point the relay already holds as an
#: answerable question would be a second, unanswerable copy of it on the channel.
NOTIFY_GRACE_S = 3.0
_HELD_KINDS = ("permission", "continuation")


def _held(session_id: str, base: Optional[Path]) -> bool:
    try:
        record = json.loads(waiting_path(session_id, base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(record, dict) and record.get("kind") in _HELD_KINDS


def notify(hook_input: Dict[str, Any], *,
           get: Getter = local_config.get,
           run: Callable[[str, str], int] = _run_notify,
           post: Callable[[str, str], None] = post_webhook,
           project_name: Callable[[str], str] = _project_name,
           sleep: Callable[[float], None] = time.sleep,
           base: Optional[Path] = None) -> Optional[str]:
    """Deliver one non-question blocking message. One attempt, never waits.

    Permission prompts and waiting-for-input notices reach the outbound one way:
    there is no answer to bring back, so there is nothing to hold the session on.
    Returns None when the notification went out, else the drop reason — a log
    line, never anything the session could feel: a notify that fails must say so
    somewhere, or it reproduces exactly the silence this exists to end (B-184).
    Nothing derived from the message is persisted — no record, no file; the log
    line carries the reason and the session label, never the message text.
    """
    state = readiness(get)
    if not state["enabled"]:
        return None
    message = enrich_message(hook_input)
    session_id = str(hook_input.get("session_id") or "")
    sid = _safe_id(session_id)[:8] or "unknown"
    if state["target"] == "command" and _safe_id(session_id):
        # The record is written only after the outbound accepted the question, so a
        # notification fired at the same moment checks once more after a short grace.
        held = _held(session_id, base)
        if not held:
            sleep(NOTIFY_GRACE_S)
            held = _held(session_id, base)
        if held:
            logger.info("question relay notify [%s]: skipped — the relay holds this as an answerable question", sid)
            return None
    if not message:
        logger.warning("question relay notify [%s]: dropped — nothing to say: no message and no pending call readable", sid)
        return "nothing to say: no message and no pending call readable"
    command = _text(get(KEY_NOTIFY_COMMAND))
    webhook = _text(get(KEY_WEBHOOK))
    if not command and not webhook:
        logger.warning("question relay notify [%s]: dropped — %s is not set (and neither is %s)",
                       sid, KEY_NOTIFY_COMMAND, KEY_WEBHOOK)
        return f"missing {KEY_NOTIFY_COMMAND}"
    project = project_name(str(hook_input.get("cwd") or os.getcwd()))
    if command:
        envelope = {"kind": "notification", "project": project, "agent": f"{project} · {sid}",
                    "session_id": session_id, "message": message}
        try:
            code = run(command, json.dumps(envelope, ensure_ascii=False))
        except Exception as exc:
            logger.warning("question relay notify [%s]: outbound could not run (%s)", sid, type(exc).__name__)
            return f"outbound could not run ({type(exc).__name__})"
        if code != 0:
            logger.warning("question relay notify [%s]: outbound exited %s", sid, code)
            return f"outbound exited {code}"
    else:
        # Unlike a question, a notification HAS no options to hide behind a detail
        # setting: the message is the whole content, so it goes out in every shape.
        try:
            post(webhook, f"⚠ {project} · {sid}\n{message}"[:1900])
        except Exception as exc:
            logger.warning("question relay notify [%s]: webhook post failed (%s)", sid, type(exc).__name__)
            return f"webhook post failed ({type(exc).__name__})"
    logger.info("question relay notify [%s]: delivered (%d chars)", sid, len(message))
    return None

# --------------------------------------------------------------------------- #
# parked questions — what went to the terminal unrelayed (fleet-relay-backfill)
# --------------------------------------------------------------------------- #

#: How long a parked question is kept when nothing pulls it in. A question that old has an
#: owner who came back to the terminal, or a session that ended.
PARK_RETENTION_S = 24 * 3600


def parked_path(session_id: str, base: Optional[Path] = None) -> Path:
    return (base or state_dir()) / "parked" / f"{_safe_id(session_id)}.json"


def park(hook_input: Dict[str, Any], base: Optional[Path] = None, wall: Callable[[], float] = time.time) -> bool:
    """Record a question that went to the terminal without the relay, so a switch-on finds it.

    Measured 2026-11-24 on runtime 2.1.331: an open `AskUserQuestion` whose hook did nothing
    is NOT in the transcript until it resolves, so a later scan cannot see it. The hook is
    the one place that holds the call. The record carries the question (mode 600, beside
    the relay's other private state, never in a repository) and is removed when pulled in,
    when the session asks again, or after `PARK_RETENTION_S`. Never raises.
    """
    try:
        if hook_input.get("tool_name") != TOOL:
            return False
        tool_input = hook_input.get("tool_input") or {}
        session_id = str(hook_input.get("session_id") or "")
        tool_use_id = str(hook_input.get("tool_use_id") or "")
        if not (session_id and tool_use_id and questions_of(tool_input)):
            return False
        base = base or state_dir()
        folder = base / "parked"
        folder.mkdir(parents=True, exist_ok=True)
        now = wall()
        for old in folder.glob("*.json"):
            try:
                if now - old.stat().st_mtime > PARK_RETENTION_S:
                    old.unlink()
            except OSError:
                continue
        path = parked_path(session_id, base)
        tmp = path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"session_id": session_id, "tool_use_id": tool_use_id, "tool_input": tool_input,
                       "cwd": str(hook_input.get("cwd") or ""), "transcript": str(hook_input.get("transcript_path") or ""),
                       "parked": now}, fh, ensure_ascii=False)
        os.replace(tmp, path)
        logger.info("question relay [%s]: left to the terminal; parked for a switch-on", _safe_id(session_id)[:8])
        return True
    except Exception as exc:
        logger.warning("question relay: could not park a question (%s)", type(exc).__name__)
        return False


def unpark(session_id: str, base: Optional[Path] = None) -> None:
    try:
        parked_path(session_id, base).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("question relay: could not remove a parked question (%s)", type(exc).__name__)


def list_parked(base: Optional[Path] = None) -> List[Dict[str, Any]]:
    folder = (base or state_dir()) / "parked"
    out: List[Dict[str, Any]] = []
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and record.get("session_id") and record.get("tool_use_id"):
            out.append(record)
    return out


def relay(hook_input: Dict[str, Any], **kwargs: Any) -> Optional[Dict[str, Any]]:
    """Decide one `AskUserQuestion` call. Returns the hook output to print, or None to release.

    A question released to the terminal is parked, so the next switch-on can pull it in.
    """
    out = _relay(hook_input, **kwargs)
    if out is None and hook_input.get("tool_name") == TOOL:
        park(hook_input, kwargs.get("base"), kwargs.get("wall") or time.time)
    return out


def _relay(hook_input: Dict[str, Any], *,
          get: Getter = local_config.get,
          run: Callable[..., int] = _run_command,
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

    # target == "command": hand over, then wait. A parked question of this session is
    # obsolete: the session has moved on to this one.
    unpark(session_id, base)
    answer_dir = base / "answers"
    answer_dir.mkdir(parents=True, exist_ok=True)
    prune_answers(base, wall())
    cid = call_id(session_id, str(hook_input.get("tool_use_id") or wall()))
    envelope = build_envelope(tool_input, cid, _text(get(KEY_AUDIENCE)), f"{project} · {sid}", answer_dir)
    try:
        code = _hand(run, _text(get(KEY_COMMAND)), json.dumps(envelope, ensure_ascii=False),
                     relay_env(KIND_ASK, session_id, cwd))
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
                logger.info("question relay [%s]: no answer within %.0f s; released", sid, timeout_s(get))
                return None
            sleep(POLL_S)
    finally:
        _clear_waiting(session_id, base)


# --------------------------------------------------------------------------- #
# answerable blocking points that are not questions (B-188, B-190)
# --------------------------------------------------------------------------- #

KIND_PERMISSION = "permission"
KIND_CONTINUATION = "continuation"
PERMISSION_OPTIONS = ("Allow", "Deny")
TRANSCRIPT_TAIL = 262144


def hand_over_one(hook_input: Dict[str, Any], kind: str, question: str, options: List[str], *,
                  get: Getter, run: Callable[..., int], project_name: Callable[[str], str],
                  wall: Callable[[], float], base: Path) -> Optional[Dict[str, Any]]:
    """Hand ONE question to the two-way outbound and write its waiting record.

    The envelope and the record keep the question hook's shapes exactly (plus `kind` on
    the record), because the bridge reads both: the envelope to post, the record's
    disappearance to close the post. Returns the record, or None when nothing was handed
    over (the caller then releases). No question text is written anywhere here.
    """
    session_id = str(hook_input.get("session_id") or "")
    sid = _safe_id(session_id)[:8] or "unknown"
    state = readiness(get)
    if not (state["enabled"] and state["ready"]) or state["target"] != "command":
        return None
    cwd = str(hook_input.get("cwd") or os.getcwd())
    project = project_name(cwd)
    answer_dir = base / "answers"
    answer_dir.mkdir(parents=True, exist_ok=True)
    prune_answers(base, wall())
    cid = call_id(session_id, f"{kind}:{hook_input.get('prompt_id') or ''}:{wall()}")
    envelope = build_envelope({"questions": [{"question": question, "multiSelect": False,
                                              "options": [{"label": o} for o in options]}]},
                              cid, _text(get(KEY_AUDIENCE)), f"{project} · {sid}", answer_dir)
    try:
        code = _hand(run, _text(get(KEY_COMMAND)), json.dumps(envelope, ensure_ascii=False),
                     relay_env(kind, session_id, cwd))
    except Exception as exc:
        logger.warning("question relay %s [%s]: outbound could not run (%s); released", kind, sid, type(exc).__name__)
        return None
    if code != 0:
        logger.warning("question relay %s [%s]: outbound exited %s; released", kind, sid, code)
        return None
    record = {"session_id": session_id, "id": cid, "project": project, "cwd": cwd, "questions": 1,
              "target": "command", "started": wall(), "pid": os.getpid(), "kind": kind}
    _clear_waiting(session_id, base)
    _write_json(waiting_path(session_id, base), record)
    logger.info("question relay %s [%s]: handed over as %s; waiting", kind, sid, cid)
    return record


def record_is_own(record: Dict[str, Any], base: Path) -> bool:
    """Whether the session's waiting record is still the one this carrier wrote."""
    try:
        current = json.loads(waiting_path(str(record.get("session_id")), base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(current, dict) and current.get("id") == record.get("id")


def clear_own(record: Dict[str, Any], base: Path) -> None:
    """Remove the waiting record only while it is still this carrier's own."""
    if record_is_own(record, base):
        _clear_waiting(str(record.get("session_id")), base)


def wait_one(record: Dict[str, Any], *, get: Getter, clock: Callable[[], float],
             sleep: Callable[[float], None], base: Path,
             stale: Callable[[], Optional[str]] = lambda: None) -> Optional[str]:
    """Poll for the one answer. Returns its text, or None when released (reason logged).

    `stale` names a reason the item no longer stands (answered in the terminal, superseded)
    or returns None; it is asked every poll and once more after an answer arrived, so an
    answer racing a terminal action never acts.
    """
    sid = _safe_id(str(record.get("session_id")))[:8] or "unknown"
    kind = record.get("kind", "?")
    cid = str(record.get("id"))
    answer_dir = base / "answers"
    deadline = clock() + timeout_s(get)
    while True:
        reason = stale()
        if reason:
            logger.info("question relay %s [%s]: %s; released", kind, sid, reason)
            return None
        text = collect_answers(answer_dir, cid, 1)[0]
        if text is not None:
            answer_file(answer_dir, cid, "Q1").unlink(missing_ok=True)
            reason = stale()
            if reason:
                logger.info("question relay %s [%s]: answer arrived but %s; dropped", kind, sid, reason)
                return None
            logger.info("question relay %s [%s]: answered on the channel (%s)", kind, sid, cid)
            return text
        if not record_is_own(record, base):
            logger.info("question relay %s [%s]: waiting record replaced or removed; released", kind, sid)
            return None
        if not readiness(get)["enabled"]:
            logger.info("question relay %s [%s]: switch turned off while waiting; released", kind, sid)
            return None
        if release_path(str(record.get("session_id")), base).exists():
            logger.info("question relay %s [%s]: released from the fleet", kind, sid)
            return None
        if clock() >= deadline:
            logger.info("question relay %s [%s]: no answer within %.0f s; released", kind, sid, timeout_s(get))
            return None
        sleep(POLL_S)


def transcript_entries(path: Any, tail: int = TRANSCRIPT_TAIL) -> List[Dict[str, Any]]:
    """The parseable entries in the last `tail` bytes of a transcript ([] when unreadable)."""
    if not path:
        return []
    try:
        with open(str(path), "rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - tail))
            raw = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        logger.debug("question relay: transcript unreadable: %s", type(exc).__name__)
        return []
    out = []
    for line in raw.split("\n"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def _blocks(entry: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    content = entry.get("message", {}).get("content") if isinstance(entry.get("message"), dict) else None
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


def resolved_calls(entries: List[Dict[str, Any]], tool_name: str, tool_input: Any) -> set:
    """Ids of tool_use blocks matching (name, input) that already have a tool_result.

    Measured 2026-11-22: a dialog answered in the terminal writes a tool_result for the
    pending call either way (allowed → the result; refused → `is_error: true`). The hook
    is not stopped when that happens, so the result's appearance is its only signal.
    """
    matching = {b.get("id") for e in entries for b in _blocks(e, "tool_use")
                if b.get("name") == tool_name and b.get("input") == tool_input}
    results = {b.get("tool_use_id") for e in entries for b in _blocks(e, "tool_result")}
    return {i for i in matching & results if i}


def permission_question(project: str, sid: str, hook_input: Dict[str, Any]) -> str:
    tool = str(hook_input.get("tool_name") or "a tool")
    tool_input = hook_input.get("tool_input") if isinstance(hook_input.get("tool_input"), dict) else {}
    summary = _tool_summary({"name": tool, "input": tool_input}) or tool
    return (f"🔐 Permission asked — {project} · {sid}\n{summary}\n"
            f"Allow runs it once; Deny refuses it. Free text refuses it and passes your words to the agent.")


def permission_output(text: str) -> Dict[str, Any]:
    """Fail closed: only the literal Allow option allows."""
    answer = text.strip()
    if answer == PERMISSION_OPTIONS[0]:
        decision: Dict[str, Any] = {"behavior": "allow"}
    elif answer == PERMISSION_OPTIONS[1]:
        decision = {"behavior": "deny", "message": "The owner denied this from the relay channel."}
    else:
        decision = {"behavior": "deny",
                    "message": f"The owner answered from the relay channel instead of allowing it: \"{answer}\""}
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


def permission(hook_input: Dict[str, Any], *,
               get: Getter = local_config.get,
               run: Callable[..., int] = _run_command,
               project_name: Callable[[str], str] = _project_name,
               clock: Callable[[], float] = time.monotonic,
               wall: Callable[[], float] = time.time,
               sleep: Callable[[float], None] = time.sleep,
               read_entries: Callable[[Any], List[Dict[str, Any]]] = transcript_entries,
               base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Decide one `PermissionRequest`. Returns the hook output, or None to leave it to the terminal.

    The dialog is drawn while this waits (measured), so the terminal stays live; whichever
    side answers first wins, and a terminal answer is noticed from the transcript.
    """
    tool = hook_input.get("tool_name")
    if not tool or tool == TOOL:
        return None  # the question tool is the question relay's own
    state = readiness(get)
    if not (state["enabled"] and state["ready"]) or state["target"] != "command":
        return None  # off, incomplete, or a webhook that cannot bring an answer back
    base = base or state_dir()
    tool_input = hook_input.get("tool_input")
    transcript = hook_input.get("transcript_path")
    baseline = resolved_calls(read_entries(transcript), str(tool), tool_input)
    session_id = str(hook_input.get("session_id") or "")
    sid = _safe_id(session_id)[:8] or "unknown"
    project = project_name(str(hook_input.get("cwd") or os.getcwd()))
    record = hand_over_one(hook_input, KIND_PERMISSION, permission_question(project, sid, hook_input),
                           list(PERMISSION_OPTIONS), get=get, run=run,
                           project_name=lambda _cwd: project, wall=wall, base=base)
    if record is None:
        return None

    def stale() -> Optional[str]:
        if resolved_calls(read_entries(transcript), str(tool), tool_input) - baseline:
            return "answered in the terminal first"
        return None

    try:
        text = wait_one(record, get=get, clock=clock, sleep=sleep, base=base, stale=stale)
    finally:
        clear_own(record, base)
    return permission_output(text) if text is not None else None
