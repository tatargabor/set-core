"""Bringing a recorded list back — one project, every entry, one outcome each.

The act the roster exists for. After a reboot nothing is running, the screen is
honestly empty, and `roster.read()` holds what was there. This module turns each
recorded entry into either a resumed session or a stated reason why not.

## Why this is not in the owner service

`owner.py` says it plainly: *"a line of business logic added here is a future
outage of every running agent"*. The owner's lifetime IS the agents' lifetime —
measured: a pty-attached agent dies when its pty holder dies — so every restart
of that service kills everything it holds. Restore logic will change; the owner
must not have to restart when it does. So this module decides, and calls
`OwnerClient.recover()` for the part only the owner can do.

## The one failure that is silent, and how it is avoided

A resume against a session a live process is bound to forks the conversation
into a branch the running original never sees, with nothing reporting it. The
guard for that lives in `owner._refuse_if_the_session_is_running()` and is NOT
re-implemented here — this module asks the same question
(`discovery.live_session_ids()`), once for the whole list rather than per entry,
and the owner refuses again underneath. Two checks of one fact, deliberately:
the first turns a fork into a legible `skipped`, the second is the one that
cannot be skipped by a caller who forgets.

**Undeterminable liveness counts as live.** `live_session_ids()` returns `None`
rather than an empty set when it cannot look, and every other reader in
`discovery` flattens that into "no agents" — right for a listing, exactly
backwards here, where it would read as "nothing is running" and clear the way.

## Skipped is not failed

They are read differently and acted on differently: `failed` invites a retry,
and a retry against a live session is precisely the fork above. So an entry that
cannot be restored *for a reason the framework understands* — already running,
no transcript, a cwd that is gone — is `skipped` with that reason, and only an
unexpected refusal is `failed`.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from . import discovery, roster, scopes
from .owner_client import OwnerClient, OwnerClientError, OwnerUnavailable

logger = logging.getLogger(__name__)

STARTED = "started"
SKIPPED = "skipped"
FAILED = "failed"

#: Where a restored agent's NAME came from. Carried as a fact per entry rather
#: than left to the reader's arithmetic on two label fields, because the three
#: are different answers to the question a person actually has.
#: The recorded label was free and was used — the name survived the reboot.
RESTORED = "restored"
#: A label was recorded but something else holds it, so a free variant was
#: derived. Restore derives where a rename refuses: the alternative here is
#: losing the agent, and nobody is watching at that moment.
RENAMED = "renamed"
#: Nothing was recorded, so the name is invented. Stated so it is never read as
#: a name somebody chose.
DERIVED = "derived"

#: How many alternative labels to try when the recorded one is held. Bounded
#: because an unbounded search would turn one stuck entry into a long stall,
#: and because a third collision means something is wrong that renaming will
#: not fix.
LABEL_ATTEMPTS = 3


def _free_label(wanted: str, held: Set[str]) -> str:
    """A label the owner is not already holding.

    Derived rather than refused, because the user asked for their agents back,
    not for their names — and a name is recoverable in a way a conversation is
    not. The label actually used is reported in the outcome, so the rename is
    visible rather than silent.
    """
    if wanted not in held:
        return wanted
    for n in range(2, 2 + LABEL_ATTEMPTS):
        candidate = f"{wanted}-r{n}"
        if candidate not in held:
            return candidate
    return wanted  # let the owner refuse; a made-up name is worse than its answer


def _held_labels(client: Any) -> Set[str]:
    """Labels the owner holds right now, asked ONCE for the whole restore.

    A refusal to answer is an empty set on purpose: not knowing must not stop a
    restore, and the owner refuses a duplicate label itself. This is the one
    place where "we could not ask" may be flattened, because the authority is
    downstream and it is not optional.
    """
    try:
        return {str(a.get("label")) for a in client.list_agents() if a.get("label")}
    except OwnerClientError as exc:
        logger.warning("fleet restore: cannot list held labels (%s); relying on the owner to refuse", exc)
        return set()


def _outcome(entry: Dict[str, Any], status: str, reason: Optional[str] = None,
             **extra: Any) -> Dict[str, Any]:
    return {
        "key": entry.get("key"),
        "session_id": entry.get("session_id"),
        "label": entry.get("label"),
        "cwd": entry.get("cwd"),
        "last_seen": entry.get("last_seen"),
        "status": status,
        "reason": reason,
        **extra,
    }


def restore(
    project: str,
    *,
    known_roots: Optional[Set[str]] = None,
    client: Optional[Any] = None,
    roster_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Attempt every recorded entry for one project.

    `known_roots` is passed in rather than resolved here: this layer is
    domain-free and must not read the project registry. The caller that already
    knows which roots the screen accepts supplies them — and supplying them is
    not optional, because `POST /api/fleet/agents` refuses a cwd outside that
    set, and a second route that admits what the first refuses is the guard
    being deleted one caller at a time (measurement M2).

    Raises `OwnerUnavailable` rather than reporting per-entry failures when the
    owner cannot be reached at all: nothing was attempted, and a result listing
    N failures would say something different from the truth.
    """
    stored = roster.read(project, path=roster_path)
    entries = stored["entries"]
    if not entries:
        logger.info("fleet restore: %s has no recorded entries; nothing attempted", project)
        return {"project": project, "attempted": 0, "started": [], "skipped": [], "failed": [],
                "record_exists": stored["record_exists"]}

    client = client or OwnerClient()
    # Fail here, before any entry is attempted — an unreachable owner is one
    # answer about the whole request, not N answers about N entries.
    client.health()

    live = discovery.live_session_ids()
    held = _held_labels(client)

    started: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for entry in entries:
        session_id = entry.get("session_id")
        cwd = entry.get("cwd") or ""

        if not entry.get("resumable"):
            skipped.append(_outcome(entry, SKIPPED, entry.get("not_resumable_reason")
                                    or "not resumable"))
            continue
        if live is None:
            skipped.append(_outcome(
                entry, SKIPPED,
                "cannot determine whether this session is running; treated as live — "
                "a resume against a live session forks its conversation silently"))
            continue
        if session_id in live:
            skipped.append(_outcome(
                entry, SKIPPED,
                f"session {session_id} is bound to a live process; left alone — "
                "a resume against a live session forks its conversation silently"))
            continue
        if not os.path.isdir(cwd):
            skipped.append(_outcome(entry, SKIPPED, f"its directory is gone: {cwd}"))
            continue
        if known_roots is not None and os.path.realpath(cwd) not in known_roots:
            skipped.append(_outcome(
                entry, SKIPPED,
                f"{cwd} is not a project this screen knows; register it first"))
            continue

        # Three cases that used to read alike, and the difference is what the
        # reader is actually asking about when they look at a restored fleet:
        # is this the name I gave it? A derived name presented as a restored one
        # is the false-value class, in the one place a person looks to recognise
        # their own work.
        recorded = entry.get("label")
        wanted = str(recorded) if recorded else f"{project}-restored"
        label = _free_label(wanted, held)
        name_source = (
            RESTORED if recorded and label == wanted
            else RENAMED if recorded
            else DERIVED
        )
        try:
            agent = client.recover(
                unit=scopes.unit_name(label),
                session_id=str(session_id),
                cwd=cwd,
                label=label,
                # No resume_argv: the owner's own default is used, so this cannot
                # drift from the argv a bare interactive session gets.
            )
        except OwnerUnavailable:
            # The owner went away mid-restore. Everything after this would fail
            # the same way, so say so once rather than N times.
            raise
        except OwnerClientError as exc:
            failed.append(_outcome(entry, FAILED, str(exc), attempted_label=label))
            logger.warning("fleet restore: %s (%s) refused: %s", label, session_id, exc)
            continue
        held.add(label)
        started.append(_outcome(entry, STARTED, None, label_used=label,
                                pid=agent.get("pid"), unit=agent.get("unit"),
                                renamed=label != wanted, wanted_label=wanted,
                                name_source=name_source))
        logger.info("fleet restore: %s resumed session %s as %s (pid %s)",
                    project, session_id, label, agent.get("pid"))

    logger.info("fleet restore: %s — %s started, %s skipped, %s failed of %s attempted",
                project, len(started), len(skipped), len(failed), len(entries))
    return {
        "project": project,
        "attempted": len(entries),
        "started": started,
        "skipped": skipped,
        "failed": failed,
        "record_exists": stored["record_exists"],
        # Stated rather than left to the reader's arithmetic: a restore where
        # anything did not start is a PARTIAL result, and the surface must not
        # be able to render it as a completed one by counting only `started`.
        "complete": len(started) == len(entries),
    }
