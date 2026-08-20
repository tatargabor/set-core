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
- **decision** — the work-cycle engine set a unit aside on a question and wrote
  the marker into the change's own task file. Added 2026-08-19 (task 9.15) after
  measuring that the three kinds above read only the ORCHESTRATION STATE FILE and
  were blind to this one entirely. It is the ordinary shape of stopped work: the
  question outlives the run that asked it, so by the time anyone looks there is
  no process, no state entry, and nothing on any agent tile.

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
import re
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
    #: `<change>#<task>` keys the engine marked as awaiting a human answer, read
    #: from the change's own task file. Durable by construction — the marker is
    #: written into the plan, not into runtime state, which is why it survives the
    #: run and why nothing else on this screen could see it.
    decision: List[str] = field(default_factory=list)
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
        return len(self.manual) + len(self.stalled) + len(self.orphaned) + len(self.decision)

    def as_dict(self) -> Dict[str, object]:
        return {
            "manual": self.manual,
            "stalled": self.stalled,
            "orphaned": self.orphaned,
            "decision": self.decision,
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


#: The engine's marker for a task awaiting a human answer.
#:
#: ⚠ SECOND COPY of `set_workcycle.connector._AWAITING_RE`, because `set_orch`
#: may not import the engine (design D10) — the same seam `fleet/purpose.py`
#: crosses. `tests/unit/test_fleet_awaiting.py` imports both and fails when they
#: diverge; a comment asking for them to be kept in step would not.
_AWAITING_MARKER = re.compile(r"<!--\s*awaiting:\s*(?P<question>.*?)\s*-->")

#: Inline code and fenced code, which is where the marker is TALKED ABOUT.
#:
#: A task file documenting the mechanism writes the marker between backticks, and
#: the scanner reads its own documentation as a live question — measured
#: 2026-08-20 on this repo: `fleet-view#9.15`, a task explaining that
#: `connector.mark_awaiting` writes `<!-- awaiting: … -->`, was the whole of
#: set-core's "1 waiting for a human". Same class as a quoted verdict parsed as a
#: verdict: the file describing the mechanism is inside the corpus the mechanism
#: scans.
#:
#: Stripping is safe in the direction that matters. The marker is written by a
#: PROGRAM, into a task line, never inside backticks — so nothing real is lost,
#: while every mention of it in prose stops counting.
_INLINE_CODE = re.compile(r"`+[^`]*`+")
_FENCE = re.compile(r"^\s*(```|~~~)")

#: A task whose box is ticked. Nobody is waiting on work that is finished.
#:
#: `[~]` and `[?]` are deliberately NOT here: they mean in progress and
#: uncertain, and a question recorded against either is still open. Only `x`
#: closes.
_DONE_TASK = re.compile(r"^\s*[-*]\s*\[[xX]\]")

#: Where a project keeps its changes. Overridable because a project may not use
#: the default, and guessing would report `0 awaiting` for a project that has
#: plenty — a zero from looking in the wrong place.
CHANGES_REL = os.path.join("openspec", "changes")


def open_decisions(project_root: str, *, changes_rel: str = CHANGES_REL) -> List[str]:
    """`<change>#<task>` for every task marked as awaiting a human answer.

    Read from the task files themselves rather than from any runtime record,
    because that is where the engine puts it and because it is the only carrier
    that outlives the run. A project with no changes directory returns an empty
    list — which the caller must not confuse with "not measured"; that
    distinction is carried by `source_missing` for the state file and stated
    here for the same reason.
    """
    root = os.path.join(project_root, changes_rel)
    if not os.path.isdir(root):
        return []
    found: List[str] = []
    try:
        names = sorted(os.listdir(root))
    except OSError as exc:
        logger.warning("fleet awaiting: cannot list changes: %s", exc)
        return []
    for change in names:
        if change == "archive":
            continue
        path = os.path.join(root, change, "tasks.md")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        fenced = False
        for line in text.splitlines():
            # A fenced block is an example, not a record. Toggled rather than
            # matched, because the opening and closing fences are the same token.
            if _FENCE.match(line):
                fenced = not fenced
                continue
            if fenced:
                continue
            # The marker as DATA, not as prose about the marker — see
            # `_INLINE_CODE`.
            if not _AWAITING_MARKER.search(_INLINE_CODE.sub("", line)):
                continue
            # A finished task is not waiting for anybody. The box is read, not
            # assumed: `[x]`, `[ ]` and `[~]` were all treated identically, so a
            # question answered long ago kept the project on the header's
            # "waiting for a human" count — work invented rather than reported,
            # which is the direction that makes a real signal ignored.
            if _DONE_TASK.match(line):
                continue
            # The TASK NUMBER, so the key matches what the connector writes an
            # answer under. A marker on a line with no number is still an open
            # decision, so it is kept and named by its change — dropping it would
            # be the false absence this whole module exists against.
            m = re.match(r"^\s*-\s*\[[ xX~?]\]\s+(\d+(?:\.\d+)+)\b", line)
            found.append(f"{change}#{m.group(1)}" if m else change)
    return found


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


def awaiting_for(project_name: str, *, data_dir: Optional[str] = None,
                 project_root: Optional[str] = None) -> Awaiting:
    """What this project is waiting on a human for, from BOTH carriers.

    The orchestration state file answers for runs; the change task files answer
    for decisions, and the second is the one that survives the run. Reading only
    the first — which is what this did until 2026-08-19 — renders the ordinary
    shape of stopped work as nothing to do.
    """
    out = read_awaiting(state_file_for(project_name, data_dir=data_dir))
    if project_root:
        out.decision = open_decisions(project_root)
    return out
