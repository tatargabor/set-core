"""What in a project is waiting for a HUMAN — task 7.14.

This module exists because the screen it feeds gets one case wrong by
construction. A fleet view lists running agents, so it answers *who is
working*; the question worth asking is *where has work stopped*, and stopped
work usually has nobody standing on it. A project blocked on a decision has no
process alive and no agent tile to render — so counted by agents it is
indistinguishable from a project with nothing to do, while being the one
project on the screen a person could unblock in a minute.

## Three kinds, kept apart on purpose

They are three different claims and a reader acts on them differently, so they
are never summed into one "blocked":

- **manual** — the plan itself declares a step no agent can take (an API key, an
  OAuth registration, a DNS record). A *declaration*, and the only one of the
  three that is honest about itself.
- **stalled** — the engine marked the change stalled. Also recorded, but by the
  machinery rather than by the plan.
- **orphaned** — the state says `running` and the recorded process is **gone**.
  This one is MEASURED, and it is the dangerous case: nothing wrote it down,
  nothing will, and it reads as work in progress forever.

## The fourth value, and why it is not counted

A `running` change whose pid IS alive is reported as `unverifiable`, never as
fine. A pid is recycled, so "a process holds that number" is not "your process
is alive" — the proxy-instead-of-the-thing defect this repository keeps
finding. Reporting it as live would be a claim; reporting it as orphaned would
be a false alarm. So it is carried, named, and left out of the total: the
surface can show it as unknown, which is what it is.

`source_missing` is the same discipline one level up: a project with no state
file at all has not been measured, and that is not the same as a project with
nothing awaiting. A zero with no source behind it is the false-absence class.

## Confidentiality

Change NAMES are carried, and a change name is authored inside a consumer's own
planning documents. This is display data read at request time — it must not be
logged, cached to disk, or written into any committed artifact. Nothing here
persists anything; the cache below holds parsed counts in memory only, keyed by
the state file's mtime, and is dropped when the process exits.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Statuses that mean the engine believes this change is in flight. A change in
#: one of these with a dead process is the orphan case above.
IN_FLIGHT = frozenset({"running", "dispatched"})

#: Statuses that mean the change is finished as far as this question goes. A
#: merged change with `has_manual_tasks` is not awaiting anybody.
SETTLED = frozenset({"merged", "done", "archived"})


@dataclass
class Awaiting:
    """What one project is waiting on a human for."""

    manual: List[str] = field(default_factory=list)
    stalled: List[str] = field(default_factory=list)
    orphaned: List[str] = field(default_factory=list)
    #: Marked in flight, pid alive — but a pid is not an identity. Named, not counted.
    unverifiable: List[str] = field(default_factory=list)
    #: No orchestration state was found. NOT the same as "nothing is awaiting".
    source_missing: bool = False

    @property
    def total(self) -> int:
        """How many things a person could act on.

        `unverifiable` is deliberately excluded: it is an admission, not a
        finding, and a count that includes admissions cannot be trusted to
        drop to zero when the work is actually done.
        """
        return len(self.manual) + len(self.stalled) + len(self.orphaned)

    def as_dict(self) -> Dict[str, object]:
        return {
            "manual": self.manual,
            "stalled": self.stalled,
            "orphaned": self.orphaned,
            "unverifiable": self.unverifiable,
            "source_missing": self.source_missing,
            "total": self.total,
        }


def _pid_alive(pid: object) -> Optional[bool]:
    """True, False, or None when the question cannot be asked.

    None for a pid that was never recorded — which must not collapse into
    False, because "no pid was written down" and "the process is gone" lead to
    different conclusions and only the second one is a finding.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None
    return os.path.isdir(f"/proc/{pid}")


#: Parsed results keyed by state-file path → (mtime, size, Awaiting).
#:
#: Keyed on BOTH mtime and size because mtime has one-second granularity on
#: some filesystems, and this repository has already been bitten by an
#: invalidation that compared too little (see the bytecode note in
#: `.claude/rules/evidence-discipline.md`). Two writes inside one second that
#: changed the file's length would otherwise reuse a stale parse.
_CACHE: Dict[str, Tuple[float, int, Awaiting]] = {}


def read_awaiting(state_file: str) -> Awaiting:
    """Read one project's orchestration state and report what awaits a human.

    Never raises: an unreadable or malformed state file yields
    `source_missing`, because a screen that fails to render because one project
    of forty has a broken file is worse than one that says so about that
    project.
    """
    try:
        stat = os.stat(state_file)
    except OSError:
        return Awaiting(source_missing=True)

    cached = _CACHE.get(state_file)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]

    try:
        with open(state_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        # The shape of the failure, never the content — a state file is full of
        # a consumer's own change names and scopes.
        logger.warning(
            "fleet awaiting: cannot read a state file (%s); reporting it as unmeasured",
            type(exc).__name__,
        )
        return Awaiting(source_missing=True)

    result = _classify(data)
    _CACHE[state_file] = (stat.st_mtime, stat.st_size, result)
    return result


def _classify(data: object) -> Awaiting:
    if not isinstance(data, dict):
        return Awaiting(source_missing=True)
    changes = data.get("changes")
    if not isinstance(changes, list):
        return Awaiting(source_missing=True)

    out = Awaiting()
    for change in changes:
        if not isinstance(change, dict):
            continue
        name = change.get("name")
        if not isinstance(name, str) or not name:
            continue
        status = change.get("status")

        if status in SETTLED:
            # A merged change's manual step was either done or overtaken; either
            # way nobody is waiting on it, and listing it forever is how a
            # counter becomes decoration.
            continue

        if change.get("has_manual_tasks"):
            out.manual.append(name)

        if status == "stalled":
            out.stalled.append(name)
            continue

        if status in IN_FLIGHT:
            # The change's own worker first; the orchestrator is the fallback,
            # because a change dispatched before the worker was recorded has
            # only the run-level pid to go on.
            alive = _pid_alive(change.get("ralph_pid"))
            if alive is None:
                alive = _pid_alive(data.get("orchestrator_pid"))
            if alive is False:
                out.orphaned.append(name)
            elif alive is True:
                out.unverifiable.append(name)
            else:
                # No pid anywhere. The engine says in flight and named nobody,
                # so nothing can be checked — an admission, not a finding.
                out.unverifiable.append(name)

    return out


def state_file_for(project_name: str, *, data_dir: Optional[str] = None) -> str:
    """Where a project's orchestration state lives.

    Resolved by name rather than through `SetRuntime`, because that class
    migrates a legacy directory as a side effect of being constructed — a read
    path that moves files is not something a screen refresh should do.
    """
    root = data_dir or os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share"),
        "set-core",
    )
    return os.path.join(root, "runtime", project_name, "orchestration", "state.json")


def awaiting_for(project_name: str, *, data_dir: Optional[str] = None) -> Awaiting:
    return read_awaiting(state_file_for(project_name, data_dir=data_dir))
