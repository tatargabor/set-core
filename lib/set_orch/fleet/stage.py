"""Where an agent sits in its work's FLOW, read from evidence — the stage axis.

The fleet screen shows who is running and whether they are waiting; this adds
the one fact a reader actually opens it for: *what is this agent working
through, and where is it in that*. The answer is a FLOW (an ordered list of
stage names) and a POSITION in it, resolved per agent session — never per
project, because two agents of one project on two changes must not be
collapsed into one row's truth.

## Two sources of the flow, and the precedence between them

- **Derived (the default, and the zero-declaration path):** the project's own
  `openspec/changes/` tree. A change directory is a physical fact — its
  artifacts exist or they do not, its tasks are checked or they are not — so
  any project using OpenSpec gets agent stages without declaring anything. A
  project mid-implementation is asked for nothing.
- **Declared:** a producer that already publishes a stage order through the
  project-status contract (`stageOrder` on a field, see
  `set_orch.project_status`) has declared ITS OWN flow, and it replaces the
  derived one for that project's agents wholesale. The framework renders
  stages; it does not know what they mean. Declared replaces derived per
  project and TOTAL — mixing half a declared flow with half a derived one is
  the partial-order false value the stage-order work rejected by name.

## The refusals, inherited from `purpose`

- **A gap is stated, never filled.** No join, no flow, no position — each is
  its own named reason on the payload. A likely guess is a fabricated value
  wearing evidence's clothes.
- **Nothing derived is written down.** A change name is authored inside a
  consumer's planning documents. Read at request time, shown, never logged,
  cached past the request's own lifetime, or committed — the same boundary
  `purpose` and the log excerpt travel under. (The one exception is the
  bounded in-memory memo on the session→change inference, below, which holds
  a slug for seconds and exists to keep a per-poll read bounded.)

## Confidentiality

Change names and producer stage values are the project's own vocabulary. They
reach the payload because the payload exists to carry them; they must not
reach a log line. Everything this module logs is a count, a shape, or a path
it declined to read.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .purpose import CHANGES_REL, Progress, Purpose, read_progress

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_FLOW",
    "Stage",
    "derive_position",
    "has_active_changes",
    "infer_change_from_session",
    "declared_axis_from_results",
    "resolve_stage",
]

#: The derived flow — the OpenSpec lifecycle, in the order the artifacts are
#: produced. Position names come from THIS tuple, never spelled a second time.
DEFAULT_FLOW: Tuple[str, ...] = ("proposal", "design", "apply", "verify", "archive")

#: Join states. `resolved` — a position in a flow, possibly marked `outside`
#: it. `gap` — no position, and WHY is on `reason`: a gap that cannot say what
#: kind of gap it is reads as one undifferentiated failure, which is how a
#: screen stops being believed.
STATE_RESOLVED = "resolved"
STATE_GAP = "gap"

REASON_NOTHING_STARTED = "nothing-started"
REASON_JOIN_FAILED = "join-failed"
REASON_NO_FLOW = "no-flow"
REASON_NO_POSITION = "no-position"


@dataclass(frozen=True)
class Stage:
    """One agent's position in its work's flow, or the named reason there is none."""

    state: str
    flow: Optional[Tuple[str, ...]] = None
    position: Optional[str] = None
    reason: Optional[str] = None
    #: `derived` — read off the project's openspec tree. `declared` — the
    #: producer's own contract answer. Carried so a reader can tell whose
    #: vocabulary the strip is speaking.
    source: Optional[str] = None
    #: The position was resolved but does not appear in the flow. Present and
    #: MARKED, never dropped: an unexplained value dropped is a producer's
    #: stage silently vanishing because the framework did not predict it.
    outside: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "flow": list(self.flow) if self.flow else None,
            "position": self.position,
            "reason": self.reason,
            "source": self.source,
            "outside": self.outside,
        }


def derive_position(project_root: str, change: str) -> Optional[str]:
    """One change's stage, from its artifacts alone. The design's mapping table.

    First matching rule wins:

    | evidence                                          | stage      |
    |---------------------------------------------------|------------|
    | directory only under `changes/archive/`           | `archive`  |
    | `tasks.md` present, ≥1 unchecked numbered task    | `apply`    |
    | `tasks.md` present, all numbered tasks checked    | `verify`   |
    | no `tasks.md`, design artifact present            | `design`   |
    | proposal only                                     | `proposal` |
    | directory with no recognizable artifact           | `None`     |

    The NUMBERED task is what makes a task line a task, not a checkbox: this
    repository's own task files carry acceptance criteria in the same `- [ ]`
    shape, and counting them would hold a fully-implemented change in `apply`
    forever. `read_progress` already draws that line and is reused rather than
    re-drawn. When a change's tasks carry no numbers at all — a producer with
    plain checkboxes — the fallback is the raw unchecked-line count, which is
    the shell phase machine's own semantics (`lib/loop/prompt.sh`).

    A change directory with NO recognizable artifact resolves to no position,
    not to `proposal`: a directory is not evidence of a proposal.
    """
    if not change or not project_root:
        return None
    changes_dir = Path(project_root) / CHANGES_REL
    active = changes_dir / change
    if active.is_dir():
        return _position_from_dir(active, project_root)
    if not changes_dir.is_dir():
        return None
    archive = changes_dir / "archive"
    if not archive.is_dir():
        return None
    # Both layouts exist in the wild: `archive/<change>` and `archive/<date>-<change>`.
    if (archive / change).is_dir():
        return "archive"
    for candidate in archive.glob(f"*-{change}"):
        if candidate.is_dir():
            return "archive"
    return None


def _position_from_dir(change_dir: Path, project_root: str) -> Optional[str]:
    if (change_dir / "tasks.md").is_file():
        # A tasks.md that cannot be read is a measurement failure, not a zero —
        # `measured: False` falls through to no position rather than to a stage.
        counts = read_progress(project_root, change_dir.name)
        if counts.measured:
            if counts.total > 0:
                return "apply" if counts.done < counts.total else "verify"
        # No NUMBERED tasks — fall back to raw checkbox lines, the shell
        # machine's semantics, for a producer that numbers nothing.
        try:
            text = (change_dir / "tasks.md").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        unchecked = sum(
            1 for line in text.splitlines() if re.match(r"^\s*-\s*\[\s*\]", line)
        )
        return "apply" if unchecked > 0 else "verify"
    if not (change_dir / "proposal.md").is_file():
        return None
    has_design = (change_dir / "design.md").is_file() or (change_dir / "specs").is_dir()
    return "design" if has_design else "proposal"


def has_active_changes(project_root: str) -> bool:
    """Whether ANY change directory sits un-archived under the project's tree."""
    changes_dir = Path(project_root) / CHANGES_REL
    if not changes_dir.is_dir():
        return False
    for entry in changes_dir.iterdir():
        if entry.is_dir() and entry.name != "archive":
            return True
    return False


# --------------------------------------------------------------------------- #
# Session → change inference
# --------------------------------------------------------------------------- #

#: Patterns that embed a change name in a session's own record. Two families:
#: explicit invocations (`/opsx:apply <name>`, `--change <name>`, a
#: `"change_name"` key) and PATH mentions (`openspec/changes/<name>`), which is
#: what an apply loop's tool calls are full of long after its opening prompt.
#: Path mentions must NOT match under `archive/` — an archived change is done,
#: and naming it is remembering, not working on it.
_OPSX = re.compile(r"/opsx:\w+\s+([a-z0-9][a-z0-9-]+)")
_CHANGE_KEY = re.compile(r'"change_name":\s*"([^"]+)"')
_CHANGE_BRANCH = re.compile(r"\bchange/([a-z0-9][a-z0-9-]+)")
_CHANGES_PATH = re.compile(r"openspec/changes/(?!archive)([a-z0-9][a-z0-9-]+)")
_CHANGE_ARG = re.compile(r"--change[= ]([a-z0-9][a-z0-9-]+)")
_PATTERNS = (_OPSX, _CHANGE_KEY, _CHANGE_BRANCH, _CHANGES_PATH, _CHANGE_ARG)

#: What is read of a session record: its head AND its tail. The invocation that
#: names the change is where a session STARTS — but a session that has been
#: running for days names its CURRENT change in its recent activity, and its
#: head may hold nothing but a long-gone first task. Measured on a live session
#: (2026-08-30, 732 KB): the head yielded a change mentioned once and long
#: since left; the tail named the change actually in flight, three ways.
#: The whole transcript is NOT read — per agent per poll that would make the
#: fleet endpoint pay for megabytes to learn one slug.
_INFERENCE_WINDOW_BYTES = 262_144

#: A tiny memo so a 5 s poll does not re-read the same windows. Seconds, not
#: minutes — a resumed session changes identity, and the memo must not outlive
#: the file it describes. Keyed on the file's own fingerprint; holds a slug,
#: never content. Same precedent as the status contract's in-memory answer
#: cache, and the same boundary: it never reaches a log or a disk.
_INFERENCE_MEMO: Dict[Tuple[str, int, int], Tuple[float, Optional[str]]] = {}
_INFERENCE_MEMO_TTL = 10.0
_INFERENCE_MEMO_MAX = 256


def infer_change_from_session(session_log: Optional[str]) -> Optional[str]:
    """The change name a session's own record names MOST RECENTLY, or `None`.

    Two bounded windows — head and tail — and across both, the LAST match
    wins: recency is the whole point. A miss is a MISS — the caller reports a
    gap rather than guessing from the project's changes.
    """
    if not session_log:
        return None
    try:
        st = Path(session_log).stat()
    except OSError:
        return None
    key = (session_log, st.st_mtime_ns, st.st_size)
    now = time.monotonic()
    hit = _INFERENCE_MEMO.get(key)
    if hit and now - hit[0] < _INFERENCE_MEMO_TTL:
        return hit[1]
    size = st.st_size
    windows: list = []
    try:
        with open(session_log, "rb") as fh:
            head = fh.read(_INFERENCE_WINDOW_BYTES)
            windows.append((0, head))
            if size > _INFERENCE_WINDOW_BYTES:
                fh.seek(max(0, size - _INFERENCE_WINDOW_BYTES))
                tail = fh.read()
                windows.append((size - len(tail), tail))
    except OSError as exc:
        logger.debug("fleet stage: session record unreadable (%s)", type(exc).__name__)
        return None

    # Every match carries its absolute offset; the largest offset is the most
    # recent naming. A name mentioned recently beats a name mentioned first.
    best: tuple = None
    for base, window in windows:
        text = window.decode("utf-8", errors="replace")
        for pattern in _PATTERNS:
            for m in pattern.finditer(text):
                cand = (base + m.start(), m.group(1))
                if best is None or cand[0] > best[0]:
                    best = cand
    found = best[1] if best else None
    if len(_INFERENCE_MEMO) >= _INFERENCE_MEMO_MAX:
        _INFERENCE_MEMO.clear()
    _INFERENCE_MEMO[key] = (now, found)
    return found


# --------------------------------------------------------------------------- #
# The declared flow, from a project-status answer
# --------------------------------------------------------------------------- #

def declared_axis_from_results(results: Iterable[Any]) -> Optional[Tuple[List[str], Dict[str, str]]]:
    """The declared flow and a change→stage index, from contract answers.

    A result carries the declaration when its envelope declares a field with a
    `stageOrder` role; validation and all-or-nothing semantics are the
    contract's own (`project_status._display_roles` → `_stage_list`), reused —
    this module adds a READER, not a second vocabulary. The first answer that
    declares one wins: two answers declaring different orders is a producer
    inconsistency this module will not adjudicate.

    The index maps the answer's own identifier (the field the envelope declared
    as `id`) to that item's stage value, because that is the only join the
    producer has offered: an agent's change name against the id the producer
    publishes. An item with a stage but no id, or an id but no stage, joins
    nothing — and nothing is inferred to fill it.
    """
    from ..project_status import LIST_ROLES, _display_roles  # local: keeps the module import-light

    for result in results:
        if not getattr(result, "ok", False):
            continue
        display = getattr(result, "display", None)
        data = getattr(result, "data", None)
        roles = _display_roles(display)
        stage_field = next(
            (name for name, role in roles.items()
             if isinstance(role, dict) and set(role).issubset(LIST_ROLES) and role),
            None,
        )
        if stage_field is None:
            continue
        (form, stages), = roles[stage_field].items()
        id_field = next(
            (name for name, role in roles.items() if role == "id" and name != stage_field),
            None,
        )
        index: Dict[str, str] = {}
        if id_field is not None:
            _index_items(data, stage_field, id_field, index)
        return list(stages), index
    return None


def _index_items(value: Any, stage_field: str, id_field: str, index: Dict[str, str]) -> None:
    """Every item carrying BOTH the stage and the id, at any depth."""
    if isinstance(value, list):
        for item in value:
            _index_items(item, stage_field, id_field, index)
        return
    if not isinstance(value, dict):
        return
    stage = value.get(stage_field)
    ident = value.get(id_field)
    if isinstance(stage, str) and stage.strip() and isinstance(ident, (str, int)) \
            and not isinstance(ident, bool):
        index[str(ident)] = stage
    for child in value.values():
        _index_items(child, stage_field, id_field, index)


# --------------------------------------------------------------------------- #
# The join, per agent
# --------------------------------------------------------------------------- #

def _joined_change(purposes: Optional[List[Purpose]], pid: int,
                   session_id: Optional[str]) -> Optional[str]:
    """The change a work-cycle record binds to THIS agent, or `None`.

    The record is the reliable half of the join: the engine wrote it while the
    unit ran. A RUNNING record only — a finished or stale record describes a
    run that is over, and lending it to a live agent would put a completed
    stage on a session that is doing something else now.
    """
    if not purposes:
        return None
    for p in purposes:
        if p.status != "running":
            continue
        if (session_id and p.session_id and p.session_id == session_id) or p.pid == pid:
            return p.change or None
    return None


def _gap(reason: str, flow: Optional[Tuple[str, ...]], source: Optional[str]) -> Stage:
    return Stage(state=STATE_GAP, flow=flow, position=None, reason=reason,
                 source=source)


def resolve_stage(
    project_root: Optional[str],
    purposes: Optional[List[Purpose]],
    pid: int,
    session_id: Optional[str],
    session_log: Optional[str],
    declared: Optional[Tuple[List[str], Dict[str, str]]] = None,
) -> Stage:
    """One agent's stage, by the precedence the design fixes.

    Declared flow when the project declared one; derived from the openspec
    tree otherwise; an explicit gap with a NAMED reason when neither evidence
    nor the join resolves. Nothing here writes anything down.
    """
    if declared is not None:
        flow_list, index = declared
        flow = tuple(flow_list)
        change = _joined_change(purposes, pid, session_id)
        if change is None:
            change = infer_change_from_session(session_log)
        if change is None:
            # No join. An empty producer index says the project itself has
            # nothing in flight; a populated one says this agent specifically
            # could not be matched — two different sentences.
            reason = REASON_NOTHING_STARTED if not index else REASON_JOIN_FAILED
            return _gap(reason, flow, "declared")
        value = index.get(change)
        if value is None:
            return _gap(REASON_JOIN_FAILED, flow, "declared")
        return Stage(
            state=STATE_RESOLVED, flow=flow, position=value,
            source="declared", outside=value not in flow,
        )

    # Derived path. No openspec tree and no declaration is a gap with a name —
    # not the absence of a field, which would read as "nothing running".
    flow = DEFAULT_FLOW
    if not project_root or not (Path(project_root) / CHANGES_REL).is_dir():
        return _gap(REASON_NO_FLOW, None, None)

    change = _joined_change(purposes, pid, session_id)
    if change is None:
        change = infer_change_from_session(session_log)
    if change is None:
        reason = (REASON_NOTHING_STARTED
                  if not project_root or not has_active_changes(project_root)
                  else REASON_JOIN_FAILED)
        return _gap(reason, flow, "derived")

    position = derive_position(project_root or "", change)
    if position is None:
        # The name was joined but no artifact backs it — an inferred name for
        # a change that never existed here, or a bare directory. A gap, not a
        # guess at the first stage.
        return _gap(REASON_NO_POSITION, flow, "derived")
    return Stage(state=STATE_RESOLVED, flow=flow, position=position, source="derived")
