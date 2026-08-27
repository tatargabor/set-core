"""The vocabulary both process-source backends share.

Kept out of `__init__` so a backend can import it without importing the
dispatcher that imports the backend — the same reason `fleet/scopes/_types.py`
exists, and the same shape.

**The one rule this module encodes, and the reason the package exists at all:**
`None` means *the question could not be answered*, and an empty container means
*it was answered and the answer is nothing*. They are never collapsed.

Two callers already act on that difference in opposite directions. A listing is
honest when it shows an empty screen — nothing was found, say so. The resume
guard is not: it refuses to resume a session something is already running, and
there an empty set means **go ahead**. An unreadable process table flattened to
an empty list would clear the way for a resume onto a live session, which forks
its conversation silently. So a backend that cannot see may not return `[]`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

#: The six facts the fleet reads about a process. Named here rather than left
#: implicit so that "the backends answer the same questions" is a check somebody
#: can run, and so that a fact the fleet needs everywhere lands in the contract
#: instead of on whichever backend happened to need it first.
#:
#: `cwd` and `argv` also have batch forms — `cwds()` and `argvs()` — which answer
#: the SAME fact for many pids in one go. They are listed separately below
#: because they are an optimisation, not a seventh and eighth question.
OPERATIONS = (
    "live_pids",   # every live pid whose executable identity is a given name
    "cwd",         # the working directory of a pid
    "argv",        # the argument vector of a pid
    "ppid",        # the parent pid of a pid
    "env_value",   # one named environment variable of a pid
    "comm",        # the executable identity of a pid
)

#: The batch forms. A backend must provide these too; on a platform where each
#: fact costs a process spawn, asking per pid is the difference between three
#: subprocesses per fleet pass and three per agent.
BATCH_OPERATIONS = ("cwds", "argvs")

#: Everything a backend must expose.
CONTRACT = OPERATIONS + BATCH_OPERATIONS

#: The default `/proc` root, and — because the callers all carry it as a default
#: argument — the value that means "no root was actually chosen, dispatch by
#: platform". See `procsource.__init__` for why that is not a fudge.
DEFAULT_PROC_ROOT = "/proc"


class ProcSourceError(RuntimeError):
    """A process fact could not be read for a reason worth naming."""


@dataclass
class ProcRow:
    """One process, as a whole-table read returns it.

    Every field is optional because the two platforms answer with different
    completeness in one pass: a `/proc` walk reads `comm` cheaply and pays per
    file for anything else, while one `ps` yields pid, ppid, comm and argv
    together. A field that was not read is `None` — never a plausible-looking
    default, which would be indistinguishable from a measurement.
    """

    pid: int
    comm: Optional[str] = None
    ppid: Optional[int] = None
    argv: Optional[List[str]] = None


@dataclass
class TableRead:
    """The result of a whole-table read: rows, or a stated failure.

    A bare `Optional[Dict]` would work, and this exists for the same reason the
    `None`/empty split does — the failure has to survive being passed around. A
    caller that receives `rows={}` and `failed=True` cannot mistake it for a
    machine with no processes on it.
    """

    rows: Dict[int, ProcRow] = field(default_factory=dict)
    failed: bool = False

    def pids_with_comm(self, name: str) -> List[int]:
        """Pids whose executable identity is `name` — identity, not substring.

        The basename is compared, for equality. Matching a command line instead
        finds every shell whose path happens to contain the word; measured at
        **31 false positives** on the machine the original reader was written
        against, all of them shell snapshots.

        The basename is taken on both platforms because they spell the same fact
        differently: Linux records a bare name truncated to 15 characters, and
        macOS reports a full executable path for many processes. Neither
        truncation nor pathing is visible for a six-character name, which is why
        this is written down rather than discovered later by a longer one.
        """
        return sorted(
            pid for pid, row in self.rows.items()
            if row.comm is not None and _basename(row.comm) == name
        )


def _basename(value: str) -> str:
    """The last path segment, whitespace-stripped. Works for a bare name too."""
    return value.strip().rsplit("/", 1)[-1]
