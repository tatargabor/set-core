"""What an agent is working TOWARDS, read from the engine's record — task 3.9.

Before this existed the screen was going to draw a field with no source. The
work-cycle engine supplies all three parts of it — which change, which group,
how far — and this module reads what the engine *recorded*, never what an agent
says about itself.

## Why nothing here imports the engine

`set_workcycle` may import `set_orch`; **`set_orch` may not import
`set_workcycle`** (engine design D10). That direction is what makes
"orchestration keeps working with the engine deleted" a fact a test can check
instead of a sentence in a comment — and one is checking:
`tests/unit/test_workcycle_dependency_direction.py` caught an earlier import in
this package before it was ever committed.

So this reads the engine's **records off disk**, which is exactly the dependency
design §8.2 sanctions: *this change reads what the engine records; the engine
knows nothing about this change*. The cost is that the on-disk layout is named
here as well as there — a second copy, and second copies drift. It is held by a
test that imports both and fails when they diverge, because a comment asking to
be believed is not a guard.

## Three things this refuses to do

- **Measure progress in turns or events.** A ticked task is movement; a turn
  count is activity, and a run going round in circles renders as progress. That
  is a false value about the one thing a reader opened the screen to check.
- **Report a dead run as live.** A record that merely *exists* proves nothing —
  it carries the pid that wrote it, and whether that process is still there is a
  question with an answer.
- **Fill a gap.** No record means no purpose is reported. On a machine with no
  engine installed that is every project, and for a while that is every machine.

## Confidentiality

A change name is authored inside a consumer's own planning documents, and a
group key names their work. Read at request time, shown, and never logged,
cached or committed — the same boundary the log excerpt travels under.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import procsource
# The agent's executable identity, imported rather than spelled a second time.
# It was the bare literal `"claude"` here and `AGENT_COMM` in `discovery`, which
# is one fact with two spellings — the kind that stays consistent right up until
# somebody changes one of them. The direction of the import is the safe one:
# `discovery` is where identity is decided and it does not read runs.
from .discovery import AGENT_COMM

logger = logging.getLogger(__name__)

__all__ = [
    "RUN_STATE_REL",
    "CHANGES_REL",
    "Progress",
    "Purpose",
    "read_purposes",
    "purpose_for_pid",
    "read_progress",
]

#: The engine's on-disk layout, named here because this package may not import
#: it. ⚠ SECOND COPY — `set_workcycle.engine.RUN_STATE_DIR` is the original, and
#: `tests/unit/test_fleet_purpose.py` fails if the two diverge.
RUN_STATE_REL = "set/runtime/work-cycle"

#: Where a change's task file lives, relative to the project root.
CHANGES_REL = "openspec/changes"

#: A numbered task line. The NUMBER is what makes it a task: this repository's
#: own task files carry acceptance criteria in the same `- [ ]` shape, and a
#: pattern without the number counts them too — measured here, 215 against 93.
_TASK = re.compile(r"^- \[( |x|X|~|\?)\] (\d+(?:\.\d+)+)\b")

#: Marks that mean the task is finished. `~` is partial and deliberately NOT
#: counted as done: a partial is a claim with a limit in it, and rounding it up
#: is how a screen reports work that is not there.
_DONE = frozenset({"x", "X"})


@dataclass(frozen=True)
class Progress:
    """How far a change has got, counted in TASKS.

    `measured` is false when the task file could not be read at all. A zero with
    `measured: false` beside it says *we looked nowhere*; a zero with
    `measured: true` says *nothing is done*. Rendering them alike is the
    false-absence class this whole screen exists for.
    """

    done: int = 0
    total: int = 0
    partial: int = 0
    measured: bool = False

    @property
    def fraction(self) -> Optional[float]:
        """`None` rather than 0.0 when there is nothing to divide by.

        A `0.0` for an unmeasured change is a number a progress bar will happily
        draw, and it looks exactly like a change nobody has started.
        """
        if not self.measured or self.total <= 0:
            return None
        return self.done / self.total

    def as_dict(self) -> Dict[str, object]:
        return {"done": self.done, "total": self.total, "partial": self.partial,
                "measured": self.measured, "fraction": self.fraction}


@dataclass
class Purpose:
    """One recorded run: what it is for, and whether it is still happening."""

    change: str
    unit_id: str = ""
    group: Optional[str] = None
    kind: Optional[str] = None
    lens: Optional[str] = None
    seat: Optional[str] = None
    pid: int = 0
    started_at: Optional[str] = None
    #: `finished` | `running` | `stale`. The third is not silence — it is a
    #: record claiming a run whose process is gone, which is the shape 7.14
    #: found on real data as 68 days of "in progress" that was not.
    status: str = "stale"
    #: The last verdict the engine recorded, as the engine wrote it. Carried
    #: rather than summarised: a summary of a verdict is a second judgement.
    verdict: Optional[dict] = None
    #: Set when the run claims to be live and the pid is held by something that
    #: is NOT an agent process. A pid is recycled, so "a process holds that
    #: number" is not "your run is alive" — and this says which question was
    #: answered rather than quietly picking one.
    pid_unverified: bool = False
    progress: Progress = field(default_factory=Progress)

    def as_dict(self) -> Dict[str, object]:
        return {
            "change": self.change, "unit_id": self.unit_id, "group": self.group,
            "kind": self.kind, "lens": self.lens, "seat": self.seat, "pid": self.pid,
            "started_at": self.started_at, "status": self.status,
            "verdict": self.verdict, "pid_unverified": self.pid_unverified,
            "progress": self.progress.as_dict(),
        }


def read_progress(project_root: str, change: str) -> Progress:
    """Completed tasks in a change's task file. Never turns, never events."""
    path = Path(project_root) / CHANGES_REL / change / "tasks.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        # Not a warning: a change with no task file is ordinary, and a log line
        # per project per poll is how a real signal gets drowned.
        logger.debug("fleet purpose: no task file at %s", path)
        return Progress(measured=False)
    done = total = partial = 0
    for line in text.splitlines():
        m = _TASK.match(line)
        if not m:
            continue
        total += 1
        if m.group(1) in _DONE:
            done += 1
        elif m.group(1) == "~":
            partial += 1
    return Progress(done=done, total=total, partial=partial, measured=True)


class _LazyTable:
    """One process-table read, taken on first use and shared afterwards.

    Not a cache with a lifetime — it lives for one `read_purposes()` call and is
    discarded. A table that outlived its pass would report an exited process as
    live, which is the direction that makes a stale run look like a running one.
    """

    def __init__(self, proc_root: str):
        self._proc_root = proc_root
        self._read = None

    @property
    def rows(self):
        if self._read is None:
            self._read = procsource.read_table(root=self._proc_root)
        return self._read.rows


def _pid_state(pid: int, proc_root: str = "/proc", table=None) -> tuple:
    """(alive, is_agent). Both questions, because they are different questions.

    Read from a process-table row rather than from `/proc/<pid>` directly, which
    is what makes this answer on a platform that has no `/proc`. Measured before
    the change, on a machine with a live agent at pid 37343: this returned
    `(False, False)` there, so **every recorded run reported `stale`** — "nothing
    is running", stated about a machine where something was.

    The row, not the identity, decides liveness. A pid that is present with an
    unreadable `comm` stays `(True, False)` — alive but unverified — exactly as
    the `/proc` version had it. Collapsing the two into "not alive" would have
    reintroduced the same false absence through a narrower door.

    `table` is the whole-table read, taken once by the caller. A failed read
    yields `(False, False)`, which keeps the existing behaviour of an unreadable
    root: a run whose liveness cannot be established is not claimed to be
    running.
    """
    if pid <= 0:
        return False, False
    if table is None:
        table = _LazyTable(proc_root)
    row = table.rows.get(pid)
    if row is None:
        return False, False
    return True, row.comm == AGENT_COMM


def _status_of(record: dict, proc_root: str, table=None) -> tuple:
    """`finished` / `running` / `stale`, and whether the pid was verified.

    Finished first, because a committed or set-aside run is finished whatever its
    pid now belongs to — and asking about the pid first would call a completed
    run stale as soon as its process exited, which is always.
    """
    if record.get("commit") is not None or record.get("set_aside") is not None:
        return "finished", False
    pid = int(record.get("pid") or 0)
    alive, is_agent = _pid_state(pid, proc_root, table)
    if not alive:
        return "stale", False
    return "running", not is_agent


def read_purposes(
    project_root: str, *, change: str = "", proc_root: str = "/proc",
    with_progress: bool = True,
) -> List[Purpose]:
    """Every run the engine recorded for this project. Empty where there is none.

    An empty list means exactly that — no record — and the caller reports no
    purpose rather than inventing one. Design §8.1: where the engine is absent
    the capability is absent, the absence is stated, and nothing is inferred to
    fill it.
    """
    root = Path(project_root) / RUN_STATE_REL
    if change:
        root = root / change
    if not root.is_dir():
        return []
    out: List[Purpose] = []
    progress_cache: Dict[str, Progress] = {}
    # One process-table read for the whole directory of records, and NONE at all
    # if no record needs it. Both halves are load-bearing: on a platform where
    # reading the table is a process spawn, once-per-record is the cost this
    # avoids — and reading it eagerly would consult the machine for a directory
    # of finished runs, which `_status_of` decides without the pid on purpose.
    table = _LazyTable(proc_root)
    for path in sorted(root.rglob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Named, not swallowed: an unreadable record is a run we cannot
            # describe, which is different from a run that is not there.
            logger.warning("fleet purpose: unreadable run record %s: %s", path.name, exc)
            continue
        if not isinstance(record, dict):
            continue
        change_name = str(record.get("change") or "")
        status, unverified = _status_of(record, proc_root, table)
        if with_progress and change_name and change_name not in progress_cache:
            progress_cache[change_name] = read_progress(project_root, change_name)
        out.append(Purpose(
            change=change_name,
            unit_id=str(record.get("unit_id") or ""),
            group=record.get("group") or None,
            kind=record.get("kind") or None,
            lens=record.get("lens") or None,
            seat=record.get("seat") or None,
            pid=int(record.get("pid") or 0),
            started_at=record.get("started_at") or None,
            status=status,
            verdict=record.get("verdict") or None,
            pid_unverified=unverified,
            progress=progress_cache.get(change_name, Progress()),
        ))
    logger.debug("fleet purpose: %d recorded runs under %s", len(out), project_root)
    return out


def purpose_for_pid(purposes: List[Purpose], pid: int) -> Optional[Purpose]:
    """The run this process is executing, or None.

    Joined on the pid the ENGINE recorded, which is the only link that exists:
    the engine writes the pid of the process running the unit. A record whose
    process is gone never matches a live agent, so a stale record cannot lend
    its purpose to whatever now holds that number.
    """
    for p in purposes:
        if p.pid == pid and p.status == "running":
            return p
    return None
