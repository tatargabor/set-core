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
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

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

#: The document-level fact this record gained on 2026-08-26: **when the fleet was
#: last observed**, stamped by the write that also stamps every entry that round
#: saw. `None` means unknown — a document written before this existed — and it is
#: never inferred from the newest entry's `last_seen`.
#:
#: The difference is the whole reason it is stored rather than derived: a machine
#: that went down with NOTHING running has a newest-`last_seen` pointing at the
#: last time something was alive, so a derived answer would present a composition
#: from days earlier as the one that was open — the false-value class, in the
#: direction that acts. The stamp answers "when was the fleet last observed"; the
#: maximum answers "when was something last alive", and only the first one is the
#: question a restore asks.
LAST_ROUND_FIELD = "last_round_at"

EMPTY: Dict[str, Any] = {"version": 1, "projects": {}, LAST_ROUND_FIELD: None}


def _now() -> float:
    return time.time()


def _no_session_key(agent: Any) -> str:
    """A key for an agent NO source knows a session id for.

    ⚠ This docstring used to claim the key is "stable across sightings" and
    derived "never from its pid". Both were false, and the tests below now hold
    what is actually true: with no name it falls back to `pid-N`, and the key
    CHANGES the moment the runtime supplies a name — so one agent could leave
    more than one entry behind. Measured 2026-08-27: 4 of 8 stored entries were
    of this kind, three of them one live session under successive pids.

    The instability is not repaired here, because it does not need to be: an
    entry of this kind can never be acted on, so it now lives only as long as its
    agent is seen (see `record`). A key that changes simply produces one row
    while the agent is around instead of a permanent pair.
    """
    label = str(getattr(agent, "name", None) or "") or f"pid-{getattr(agent, 'pid', '?')}"
    project = str(getattr(agent, "project_name", None) or getattr(agent, "cwd", "") or "?")
    return f"{NO_SESSION_KEY_PREFIX}{project}/{label}"


def _entry_from(agent: Any, *, now: float,
                labels: Optional[Dict[int, str]] = None,
                sessions: Optional[Dict[int, str]] = None,
                ) -> Optional[Tuple[str, Dict[str, Any]]]:
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
    pid = getattr(agent, "pid", None)
    # The runtime's record first, the framework's own start intent second — and
    # never the other way round. They answer different questions: what the
    # process is BOUND to now, versus what it was ASKED to resume. They can
    # disagree, and the case that produced this defect is exactly one that does
    # — an agent told to resume a session it could not claim. Where they
    # disagree, the process's own answer is the one the reader is asking about.
    session_id = getattr(agent, "session_id", None) or (sessions or {}).get(pid)
    key = str(session_id) if session_id else _no_session_key(agent)
    held = (labels or {}).get(pid)
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
        return {"version": 1, "projects": {}, LAST_ROUND_FIELD: None}
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
    # Carried explicitly, because this function REBUILDS rather than copies: a
    # field not named here is dropped on the next read-modify-write, and the
    # loss would be silent — the document would simply stop knowing when the
    # fleet was last observed, which reads exactly like a document written
    # before the field existed.
    try:
        last_round = float(raw[LAST_ROUND_FIELD])
    except (KeyError, TypeError, ValueError):
        last_round = None
    return {"version": 1, "projects": projects, LAST_ROUND_FIELD: last_round}


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


def _retire_unseen_sessionless(document: Dict[str, Any],
                               seen: Set[Tuple[str, str]]) -> int:
    """Drop every session-less entry this round did not see. Returns how many.

    Such an entry can never be acted on — there is no session to resume, and
    `read()` already reports it as unresumable. Its ONE stated purpose is the
    prefix constant's: keep the roster from claiming a smaller fleet than exists
    while an agent is live and unknown to the runtime. That purpose ends the
    moment the agent stops being seen, and until now nothing ended it — the
    entry sat out the full retention window as junk.

    Measured 2026-08-27, before this existed: **8 entries, 4 of them
    session-less**, and three of those four were one live session recorded under
    successive pids. Each was created in the window before the runtime wrote its
    per-pid record, superseded by a real entry when it did, and never removed.
    One dead row per agent, presented as fleet history.

    **The fail direction is what makes this permissible, and it is the whole
    argument.** Nothing that could have been acted on is removed: the rows that
    go are exactly the ones the read path marks unresumable for want of a session
    id. And the key is derived rather than allocated, so an agent that is still
    around reappears on the next sighting.

    ⚠ Callers: this is for a WHOLE-FLEET write only. A partial write knows
    nothing about what it did not look at, so removing on absence would delete
    live agents' rows. `record` gates it on `full_sweep`, the same flag and the
    same argument that already guards the round stamp.
    """
    retired = 0
    for project, entries in document.get("projects", {}).items():
        for key in [k for k in entries
                    if k.startswith(NO_SESSION_KEY_PREFIX) and (project, k) not in seen]:
            # Named, never silent: an entry that vanishes without a line is
            # indistinguishable from one that was never written — the reason the
            # age prune logs too.
            logger.info(
                "fleet roster: retiring %s from %s — no session id and not seen this round; "
                "it could never have been restored", key, project,
            )
            del entries[key]
            retired += 1
    return retired


def record(
    agents: Iterable[Any],
    *,
    labels: Optional[Dict[int, str]] = None,
    sessions: Optional[Dict[int, str]] = None,
    path: Optional[str] = None,
    now: Optional[float] = None,
    retention: float = RETENTION_SECONDS,
    full_sweep: bool = True,
) -> Dict[str, int]:
    """Upsert one entry per interactive agent. Returns what it did.

    `labels` maps pid -> the label the framework holds that agent under, and it
    is passed IN rather than resolved here: this module is a document, and a
    document that opens a socket to the agent owner would make every write
    depend on a service being up. `None` means the holder could not be asked.

    `sessions` maps pid -> the session the FRAMEWORK started that agent on, and
    travels the same way for the same reason — same shape, same owner answer,
    no second round trip. It fills a silence in the runtime's record and never
    overrides one. `None` (could not ask) stays distinct from `{}` (asked, holds
    nothing): the first is a gap in what is known, the second is a statement.

    Measured 2026-08-27, and this is why it exists: an agent the framework had
    started with `--resume <S>` was recorded with NO session id and the reason
    *"no session id was ever recorded for this agent"* — while the owner was
    reporting `resumed_session: <S>` for that same pid. The answer was reaching
    the caller and being dropped on the way in.

    **`full_sweep` says whether `agents` is the WHOLE fleet.** Only a whole-fleet
    pass may move `last_round_at`, because the stamp's meaning is *"everything
    running at this moment is stamped with it"*. A partial write that moved it
    would drop every agent it did not happen to include out of the composition —
    the safe direction (offering too few), but silent, and a silent wrong answer
    here is what this record exists to avoid. Today there is one caller and it
    always passes the whole fleet; that is a property of the current code, not a
    guarantee, so a partial caller has to say so and gets a stated no-stamp.

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
    seen: Set[Tuple[str, str]] = set()
    for agent in agents:
        built = _entry_from(agent, now=now, labels=labels, sessions=sessions)
        if built is None:
            skipped += 1
            continue
        key, entry = built
        project = entry["project"] or entry["cwd"]
        seen.add((str(project), key))
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

    retired = _retire_unseen_sessionless(document, seen) if full_sweep else 0
    pruned = _prune(document, now=now, retention=retention)
    if full_sweep:
        # Stamped even when this round saw NOTHING. That is not an edge case to
        # optimise away — it is the case the stamp exists for: "the fleet was
        # observed and was empty" is what distinguishes an empty composition
        # from an unobserved one, and without the write the surface would offer
        # the previous round's agents as though they were still open.
        document[LAST_ROUND_FIELD] = now
    else:
        logger.info(
            "fleet roster: partial write (%s entries); %s left at %s",
            added + updated, LAST_ROUND_FIELD, document.get(LAST_ROUND_FIELD),
        )
    _write_atomically(document, path)
    logger.debug(
        "fleet roster: recorded %s added, %s updated, %s skipped, %s pruned, %s retired -> %s",
        added, updated, skipped, pruned, retired, path,
    )
    return {"added": added, "updated": updated, "skipped": skipped,
            "pruned": pruned, "retired": retired}


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

    **`in_last_round` is what "was open" means for a record that consults
    nothing live**: the entry was still being seen when the fleet was last
    observed. `True` on equality with the document's stamp, `False` otherwise,
    and `None` for every entry when there is no stamp — never `False`, because a
    gap is not a zero and this value decides what a restore offers.

    Entries outside the last round are still returned in full. Filtering them
    would make the record claim a smaller fleet than it holds, which is the
    failure this module already refuses for unresumable entries.
    """
    path = path or default_roster_path()
    log_root = log_root or discovery.SESSION_LOG_ROOT
    unreadable = False
    try:
        document, exists = _load(path)
    except RosterUnreadable:
        document, exists, unreadable = dict(EMPTY, projects={}), True, True

    stored = document.get("projects", {}).get(project, {})
    last_round = document.get(LAST_ROUND_FIELD)
    entries: List[Dict[str, Any]] = []
    for key, entry in stored.items():
        session_id = entry.get("session_id")
        log = discovery._session_log_for(session_id, log_root) if session_id else None
        if log:
            resumable, reason = True, None
        elif not session_id:
            # Names BOTH sources on purpose. The previous wording — "no session
            # id was ever recorded for this agent" — was a denial, and it was
            # false for the one case that mattered: the framework HAD recorded
            # one, at the moment it started the agent, and was reporting it
            # elsewhere on the same screen. A reader acting on that line needs to
            # know which two places were asked, because that is what tells them
            # nothing is broken and what would change the answer.
            resumable, reason = False, (
                "no source knows a session for this agent — the runtime has no "
                "record of it and the framework did not start it"
            )
        else:
            resumable, reason = False, f"no transcript on disk for session {session_id}"
        entries.append({
            "key": key,
            **{name: entry.get(name) for name in ENTRY_FIELDS},
            "session_log": log,
            "resumable": resumable,
            "not_resumable_reason": reason,
            "in_last_round": (
                None if last_round is None
                else float(entry.get("last_seen") or 0.0) == float(last_round)
            ),
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
        # `None` means the record cannot say when the fleet was last observed.
        # The surface falls back to the whole list AND says why, rather than
        # presenting the whole list as though it were the composition.
        LAST_ROUND_FIELD: last_round,
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
