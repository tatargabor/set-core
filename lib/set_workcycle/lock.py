"""One work unit per tree, held by one **session**.

The lock is scoped to the working tree the caller hands over, never to a project or a
worktree layout. The framework's own orchestration hands the engine a worktree; a consumer
running trunk-based hands it a repository root. Neither is privileged, and the lock — not the
tree layout — is what stops two units from colliding.

**The seat is session-scoped, and that is a defect inherited on purpose.** In the proven
engine the seat identified the *project*, so it matched every live session in it — seven, on
the day it was measured — and an answer meant for one run woke a different one. A seat that
names only a project is therefore refused **at the point it is recorded**, not interpreted
later: a value that cannot mean one session must never be stored as if it could.

**A stale lock is reported as stale, not as running.** A holder whose process is gone leaves
a file that is indistinguishable from a live claim unless someone asks the operating system.
Asking is cheap; the alternative is a tree that never unblocks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = [
    "LOCK_REL",
    "Seat",
    "SeatRefused",
    "LockHeld",
    "LockState",
    "validate_seat",
    "read_lock",
    "acquire",
    "release",
]

#: Runtime state, not an install artifact: an install neither creates nor removes it.
LOCK_REL = "set/runtime/work-cycle.lock"

#: A seat must identify one session. A bare project name — letters, digits, dashes and
#: underscores with no session part — cannot, so it is refused.
_SESSION_PART = re.compile(r"session[:/=-]|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", re.IGNORECASE)


class SeatRefused(ValueError):
    """The seat offered does not identify a single agent session."""


class LockHeld(RuntimeError):
    """Another unit holds this tree's lock. The holder is named."""

    def __init__(self, state: "LockState") -> None:
        self.state = state
        super().__init__(
            f"the tree is locked by {state.seat} (pid {state.pid}, since {state.acquired_at})"
        )


@dataclass(frozen=True)
class Seat:
    """One agent session's identity, as recorded in a lock."""

    value: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return self.value


def validate_seat(seat: str) -> Seat:
    """Accept a seat that identifies one session; refuse one that identifies a project.

    The discriminator is a session marker — a `session:`-style prefix or a UUID-shaped
    segment. It is deliberately a *positive* test: "does this name a session" rather than
    "does this look like a project name". A negative test would have to enumerate every way a
    project can be named, and the one it missed would be accepted.
    """
    value = (seat or "").strip()
    if not value:
        raise SeatRefused("a seat is required; the engine does not invent one")
    if not _SESSION_PART.search(value):
        raise SeatRefused(
            f"seat {value!r} does not identify a single agent session. A seat that names "
            f"only a project matches every live session in it, and an answer then reaches "
            f"the wrong one. Use e.g. 'session:<id>' or a session UUID."
        )
    return Seat(value)


@dataclass
class LockState:
    """What a lock file says, and whether the process that wrote it is still alive."""

    seat: str
    pid: int
    acquired_at: str
    change: str = ""
    group: str = ""
    path: Optional[Path] = None

    @property
    def alive(self) -> bool:
        if self.pid <= 0:
            return False
        try:
            os.kill(self.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # The process exists and belongs to someone else. Existing is what was asked.
            return True

    @property
    def status(self) -> str:
        """`"running"` or `"stale"` — never conflated, and never inferred from the file
        merely existing."""
        return "running" if self.alive else "stale"


def _lock_path(tree: str | Path) -> Path:
    return Path(tree) / LOCK_REL


def read_lock(tree: str | Path) -> Optional[LockState]:
    """The current lock on `tree`, or `None`. A corrupt lock reads as absent, and says so."""
    path = _lock_path(tree)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("lock at %s is unreadable (%s) — treating the tree as unlocked", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    return LockState(
        seat=str(data.get("seat", "")),
        pid=int(data.get("pid", 0) or 0),
        acquired_at=str(data.get("acquired_at", "")),
        change=str(data.get("change", "")),
        group=str(data.get("group", "")),
        path=path,
    )


def acquire(
    tree: str | Path, seat: str, *, change: str = "", group: str = "",
    pid: Optional[int] = None, now: Optional[str] = None,
) -> LockState:
    """Take the tree's lock for one session, or raise `LockHeld` naming the holder.

    A **stale** lock is taken over rather than waited on: its holder is gone, and refusing
    forever because a process died is how a tree stops being usable. The takeover is logged
    at WARNING with the seat it displaced, because it is a decision, not routine.
    """
    validated = validate_seat(seat)
    path = _lock_path(tree)
    existing = read_lock(tree)
    if existing is not None:
        if existing.alive:
            logger.info("lock refused on %s: held by %s (pid %d)", tree, existing.seat,
                        existing.pid)
            raise LockHeld(existing)
        logger.warning(
            "taking over a stale lock on %s: previous holder %s (pid %d) is gone",
            tree, existing.seat, existing.pid,
        )

    state = LockState(
        seat=validated.value,
        pid=pid if pid is not None else os.getpid(),
        acquired_at=now or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        change=change, group=group, path=path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({
        "seat": state.seat, "pid": state.pid, "acquired_at": state.acquired_at,
        "change": state.change, "group": state.group,
    }, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    logger.info("lock acquired on %s by %s (pid %d)", tree, state.seat, state.pid)
    return state


def release(tree: str | Path, seat: str) -> bool:
    """Release the lock if `seat` holds it. Releasing someone else's lock is refused."""
    state = read_lock(tree)
    if state is None:
        return False
    if state.seat != seat:
        logger.warning(
            "release refused on %s: %s does not hold this lock (%s does)", tree, seat, state.seat)
        return False
    try:
        _lock_path(tree).unlink()
    except OSError as exc:
        logger.warning("could not remove lock at %s: %s", _lock_path(tree), exc)
        return False
    logger.info("lock released on %s by %s", tree, seat)
    return True
