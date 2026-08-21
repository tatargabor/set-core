"""What the fleet HAS SEEN, kept where a reboot cannot reach it.

The agent list this screen shows is discovered, not stored: identity from
`/proc/<pid>/comm`, project from `/proc/<pid>/cwd`, session id from the runtime's
record at `~/.claude/sessions/<pid>.json`. A boot destroys all three, and the
user loses the composition of their working session — which agents sat on which
project, and therefore which conversations to resume.

**Why this file exists rather than a read of the runtime's own records.**
Measured 2026-08-21 on this machine: `~/.claude/sessions` held 25 `.json`
records against **25 live pids, zero stale**. The runtime removes a record when
its session exits, so that directory is a census of the living, never a history.
And its key is a **pid**, which the kernel reuses — so even a record that
happened to survive a crash would be an unreliable name for the one case this
module exists for.

Hence: our own document, keyed on the **session id**, which is what `--resume`
takes and what the transcript is named after.

## Two properties, both failure-directional

**An entry is never dropped for being unusable.** A session whose transcript is
gone is reported as present-and-not-resumable, never filtered out. A shortened
list reads as a complete one, so filtering would tell the user a smaller fleet
existed than did — the false-absence class, in the direction where nobody goes
looking.

**Resumability is computed at READ time and never stored.** A stored boolean is
a declaration about a moment that has passed. This codebase already measured
what that costs on the runtime's own `status` field: a median of 11 hours stale
across 23 sessions, maximum 83. Transcripts get deleted; a stored `true` would
send restore at a session that is not there.

## What may be written here

Identity and timestamps only: session id, label, cwd, project, kind, first-seen,
last-seen. No transcript content, no message text, no tool output. set-core may
READ a consumer's data at runtime — that is the point of the abstraction — but
it must persist nothing derived from it, and this file is persistence.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import discovery

logger = logging.getLogger(__name__)


def default_roster_path() -> str:
    """The framework's durable per-user store — beside `fleet-layout.json`.

    Resolved the same way `layout.default_layout_path()` resolves it rather than
    imported from it: these are two documents with two lifetimes, and a shared
    resolver would make a change to one silently move the other.
    """
    root = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(root, "set-core", "fleet-roster.json")


#: How long an entry nobody has seen is kept. Beyond this it is pruned on the
#: next write, with the removal logged — an entry that vanishes silently is
#: indistinguishable from one that was never recorded.
RETENTION_SECONDS = 30 * 24 * 3600

#: The prefix for the key of an agent that has no session id. A session can be
#: alive and unknown to the runtime's records — measured twice on 2026-08-18,
#: from two unrelated causes — and dropping it would make the roster claim a
#: smaller fleet than existed. It cannot collide with a real session id, which
#: is a uuid and never contains a colon.
NO_SESSION_KEY_PREFIX = "no-session:"

#: Exactly what an entry may carry. The normaliser builds from this list rather
#: than copying an input dict, so a field added upstream — a record, a socket
#: path, a name someone chose — cannot reach the file by being passed along.
ENTRY_FIELDS = ("session_id", "label", "cwd", "project", "kind", "first_seen", "last_seen")

EMPTY: Dict[str, Any] = {"version": 1, "projects": {}}


def _now() -> float:
    return time.time()


def _no_session_key(agent: Any) -> str:
    """A stable key for an agent the runtime has no session id for.

    Stable across sightings, so the same agent does not accumulate one entry per
    discovery pass — derived from what does not change about it (its project and
    its label), never from its pid.
    """
    label = str(getattr(agent, "name", None) or "") or f"pid-{getattr(agent, 'pid', '?')}"
    project = str(getattr(agent, "project_name", None) or getattr(agent, "cwd", "") or "?")
    return f"{NO_SESSION_KEY_PREFIX}{project}/{label}"


def _entry_from(agent: Any, *, now: float,
                labels: Optional[Dict[int, str]] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """One roster entry from one discovered agent, or None if it must not be recorded.

    **The label comes from `labels` — what the FRAMEWORK holds — and never from
    `agent.name`.** Measured 2026-08-21, after the first real reboot: the
    runtime's name carries `nameSource: "derived"`, is regenerated on every
    resume, and recording it gave back `set-core-34` for an agent its user had
    named `set-core-bugfix`. The name a person chose is the one every control
    addresses; the runtime's is a generated string that a restore would hand back
    as though somebody had chosen it.

    `labels is None` means the holder could not be asked, and an empty mapping
    means it was asked and holds nothing. Both produce an entry with no label,
    which the upsert treats as "learned nothing" — so neither can overwrite a
    label already recorded.
    """
    kind = str(getattr(agent, "kind", "interactive") or "interactive")
    if kind != "interactive":
        # CB-8: `-p` subprocesses are the framework's own short-lived children,
        # not sessions anyone is sitting at. Restoring one would resume a
        # subprocess as though it were a person's conversation.
        return None
    session_id = getattr(agent, "session_id", None)
    key = str(session_id) if session_id else _no_session_key(agent)
    held = (labels or {}).get(getattr(agent, "pid", None))
    return key, {
        "session_id": str(session_id) if session_id else None,
        "label": str(held) if held else None,
        "cwd": str(getattr(agent, "cwd", "") or ""),
        "project": str(getattr(agent, "project_name", None) or "") or None,
        "kind": kind,
        "first_seen": now,
        "last_seen": now,
    }


def _normalise_entry(key: str, raw: Any) -> Optional[Dict[str, Any]]:
    """One stored entry, rebuilt field by field.

    Rebuilt rather than copied: a dict passed through would carry whatever the
    producer happened to put in it, which is how transcript content, a socket
    path or a session name reaches a file that promised to hold identity only.
    """
    if not isinstance(raw, dict):
        return None
    entry = {name: raw.get(name) for name in ENTRY_FIELDS}
    if not str(entry.get("cwd") or "").strip():
        return None
    for stamp in ("first_seen", "last_seen"):
        try:
            entry[stamp] = float(entry[stamp])
        except (TypeError, ValueError):
            return None
    entry["kind"] = str(entry.get("kind") or "interactive")
    entry["session_id"] = None if key.startswith(NO_SESSION_KEY_PREFIX) else (
        str(entry["session_id"]) if entry.get("session_id") else None
    )
    return entry


def normalise(raw: Any) -> Dict[str, Any]:
    """The stored document, or an empty one. Never raises on a shape it dislikes."""
    if not isinstance(raw, dict):
        return {"version": 1, "projects": {}}
    projects: Dict[str, Dict[str, Any]] = {}
    for project, entries in (raw.get("projects") or {}).items():
        if not isinstance(entries, dict):
            continue
        kept: Dict[str, Any] = {}
        for key, value in entries.items():
            entry = _normalise_entry(str(key), value)
            if entry is not None:
                kept[str(key)] = entry
        projects[str(project)] = kept
    return {"version": 1, "projects": projects}


class RosterUnreadable(RuntimeError):
    """The stored document exists and could not be parsed."""


def _load(path: str) -> Tuple[Dict[str, Any], bool]:
    """(document, exists). A missing file is an empty roster, never an error."""
    try:
        with open(path, encoding="utf-8") as handle:
            return normalise(json.load(handle)), True
    except FileNotFoundError:
        return dict(EMPTY, projects={}), False
    except (OSError, ValueError) as exc:
        logger.warning("fleet roster: %s is unreadable (%s); treating as empty", path, exc)
        raise RosterUnreadable(str(exc))


def _write_atomically(payload: Dict[str, Any], path: str) -> None:
    """Temp file then rename — never opened for writing in the expression that reads it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=os.path.dirname(path), prefix=".fleet-roster.", delete=False
    )
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def _prune(document: Dict[str, Any], *, now: float, retention: float) -> int:
    """Drop entries unseen beyond the bound. Returns how many went."""
    dropped = 0
    for project, entries in document.get("projects", {}).items():
        for key in [k for k, e in entries.items() if now - float(e["last_seen"]) > retention]:
            age = now - float(entries[key]["last_seen"])
            logger.info(
                "fleet roster: pruning %s from %s — unseen for %.1f days (bound %.1f)",
                key, project, age / 86400.0, retention / 86400.0,
            )
            del entries[key]
            dropped += 1
    return dropped


def record(
    agents: Iterable[Any],
    *,
    labels: Optional[Dict[int, str]] = None,
    path: Optional[str] = None,
    now: Optional[float] = None,
    retention: float = RETENTION_SECONDS,
) -> Dict[str, int]:
    """Upsert one entry per interactive agent. Returns what it did.

    `labels` maps pid -> the label the framework holds that agent under, and it
    is passed IN rather than resolved here: this module is a document, and a
    document that opens a socket to the agent owner would make every write
    depend on a service being up. `None` means the holder could not be asked.

    Raises on a write failure — the CALLER decides that discovery's answer
    survives it. Swallowing here would put the decision in the wrong place: a
    future caller that does want to know would have no way to find out.
    """
    path = path or default_roster_path()
    now = _now() if now is None else now
    try:
        document, _ = _load(path)
    except RosterUnreadable:
        # A file we cannot parse is replaced rather than appended to. Keeping it
        # would mean every future write fails on the same bad bytes.
        document = dict(EMPTY, projects={})

    added = updated = skipped = 0
    for agent in agents:
        built = _entry_from(agent, now=now, labels=labels)
        if built is None:
            skipped += 1
            continue
        key, entry = built
        project = entry["project"] or entry["cwd"]
        entries = document["projects"].setdefault(str(project), {})
        existing = entries.get(key)
        if existing:
            # first_seen is the fact that does not move. Only what we learned
            # this time may overwrite what we knew, and only when we learned it.
            existing["last_seen"] = now
            for name in ("label", "cwd", "kind", "session_id"):
                if entry[name]:
                    existing[name] = entry[name]
            updated += 1
        else:
            entries[key] = entry
            added += 1

    pruned = _prune(document, now=now, retention=retention)
    _write_atomically(document, path)
    logger.debug(
        "fleet roster: recorded %s added, %s updated, %s skipped, %s pruned -> %s",
        added, updated, skipped, pruned, path,
    )
    return {"added": added, "updated": updated, "skipped": skipped, "pruned": pruned}


def read(
    project: str,
    *,
    path: Optional[str] = None,
    log_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """One project's recorded list, with resumability measured NOW.

    Consults no live state: not `/proc`, not the runtime's per-pid records,
    nothing a reboot destroys. The one thing it does look at is the transcript,
    because that is what a resume needs and it is the question the reader is
    actually asking.
    """
    path = path or default_roster_path()
    log_root = log_root or discovery.SESSION_LOG_ROOT
    unreadable = False
    try:
        document, exists = _load(path)
    except RosterUnreadable:
        document, exists, unreadable = dict(EMPTY, projects={}), True, True

    stored = document.get("projects", {}).get(project, {})
    entries: List[Dict[str, Any]] = []
    for key, entry in stored.items():
        session_id = entry.get("session_id")
        log = discovery._session_log_for(session_id, log_root) if session_id else None
        if log:
            resumable, reason = True, None
        elif not session_id:
            resumable, reason = False, "no session id was ever recorded for this agent"
        else:
            resumable, reason = False, f"no transcript on disk for session {session_id}"
        entries.append({
            "key": key,
            **{name: entry.get(name) for name in ENTRY_FIELDS},
            "session_log": log,
            "resumable": resumable,
            "not_resumable_reason": reason,
        })
    # Newest first: the list a person recognises starts with what they had open.
    entries.sort(key=lambda e: e.get("last_seen") or 0, reverse=True)
    return {
        "project": project,
        "entries": entries,
        # An absent key is not an empty value: "we have never recorded this
        # project" and "we recorded it and it held nothing" are different, and
        # the surface says different things about them.
        "record_exists": bool(exists),
        "unreadable": unreadable,
    }


def projects(*, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every project with a non-empty record, newest first.

    This is what the empty screen needs: after a reboot no project holds an
    agent, so there is nothing in the column to click, and a per-project read
    would need a project name nobody can supply.
    """
    path = path or default_roster_path()
    try:
        document, _ = _load(path)
    except RosterUnreadable:
        return []
    out: List[Dict[str, Any]] = []
    for project, entries in document.get("projects", {}).items():
        if not entries:
            continue
        out.append({
            "project": project,
            "entries": len(entries),
            "last_seen": max(float(e["last_seen"]) for e in entries.values()),
        })
    out.sort(key=lambda p: p["last_seen"], reverse=True)
    return out


def forget(project: str, key: str, *, path: Optional[str] = None) -> bool:
    """Drop one entry. Returns whether it was there."""
    path = path or default_roster_path()
    try:
        document, _ = _load(path)
    except RosterUnreadable:
        return False
    entries = document.get("projects", {}).get(project, {})
    if key not in entries:
        return False
    del entries[key]
    _write_atomically(document, path)
    logger.info("fleet roster: forgot %s from %s", key, project)
    return True


def relabel(key: str, new_label: str, *, project: Optional[str] = None,
            path: Optional[str] = None) -> int:
    """Give the recorded entry for one session a different label.

    Written at the moment of the rename rather than left to the next recording
    pass. The pass would get there — it runs on every listing — but "it will be
    correct shortly" is a claim about a race, and the entry is the thing a reboot
    reads. A rename that survives only if nothing crashes in the next few seconds
    is not a rename that survives a reboot.

    `project` narrows the search when the caller knows it. Without it every
    project is searched, because a session id identifies an entry on its own and
    a caller that knows the session but not the project is an ordinary case —
    the pid is what the API holds, and the project comes from the same lookup
    that could have failed.

    Returns how many entries were changed, so a caller can tell "nothing to do"
    from "did nothing" — they look identical from a bare boolean.
    """
    path = path or default_roster_path()
    try:
        document, existed = _load(path)
    except RosterUnreadable:
        logger.warning("fleet roster: cannot relabel %s; the record is unreadable", key)
        return 0
    if not existed:
        return 0
    changed = 0
    for name, entries in document.get("projects", {}).items():
        if project is not None and name != project:
            continue
        entry = entries.get(key)
        if entry is None or entry.get("label") == new_label:
            continue
        logger.info("fleet roster: %s in %s relabelled %r -> %r",
                    key, name, entry.get("label"), new_label)
        entry["label"] = new_label
        changed += 1
    if changed:
        _write_atomically(document, path)
    return changed
