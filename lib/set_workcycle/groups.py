"""Task-group resolution — reading the *inside* of a change.

The framework already orders changes relative to one another. This module orders the inside
of one change: it reads a `tasks.md`, finds its groups, resolves the dependency edges between
them, decides which group may run now, and cuts the slice plus carry-over that one run
receives.

Domain-free by construction. Nothing here knows what a task means, what a project is called,
or how work is executed — the work-unit engine does that, and it is a separate concern.

**Fail-closed is the governing choice.** A group carrying no dependency annotation is treated
as depending on the one before it. From outside the file, "these are independent" and "nobody
wrote it down" are indistinguishable, and of the two possible mistakes, running things in
parallel that were not meant to be is the expensive one.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "Task",
    "TaskGroup",
    "GroupPlan",
    "DependencyCycle",
    "RunNote",
    "Slice",
    "parse_task_groups",
    "select_next_group",
    "cut_slice",
    "carry_over_for",
    "reading_list",
]

# ── markers ───────────────────────────────────────────────────────────────────────────────
#
# The vocabulary is the project's, not ours: `- [x]` done, `- [ ]` open, `- [?]` awaiting a
# person. `work-cycle-adoption` requires the engine to read a project's existing markings
# rather than demand a different notation, so these mirror `set_orch.loop_tasks`.

DONE = "done"
OPEN = "open"
AWAITING = "awaiting"

_MARKERS = (
    (re.compile(r"^\s*-\s*\[[xX]\]\s?(.*)$"), DONE),
    (re.compile(r"^\s*-\s*\[\s\]\s?(.*)$"), OPEN),
    (re.compile(r"^\s*-\s*\[\]\s?(.*)$"), OPEN),
    (re.compile(r"^\s*-\s*\[\?\]\s?(.*)$"), AWAITING),
)

#: A heading, at any level. The level is decided per file — see `_group_heading_level`.
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")

#: A heading that opens a numbered group: `## 3. Task-group resolution`, `### 3.1 Foo`.
_NUMBERED_TITLE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(.*)$")

#: `<!-- depends: 2, 3 -->`, `<!-- depends: none -->`. Case-insensitive, anywhere on its line.
_DEPENDS = re.compile(r"<!--\s*depends\s*:\s*(.*?)\s*-->", re.IGNORECASE)

#: The word that declares independence. Anything else in the annotation is a group key.
_INDEPENDENT_WORDS = frozenset({"none", "-", "nothing"})


@dataclass(frozen=True)
class Task:
    """One task line, bound to exactly one group."""

    marker: str  # DONE | OPEN | AWAITING
    text: str
    line_no: int  # 1-based, into the source file
    raw: str

    @property
    def key(self) -> str:
        """The leading identifier (`3.2`, `AC-14`) if the line carries one, else ``""``."""
        m = re.match(r"^([A-Za-z]*-?\d+(?:\.\d+)*)\b", self.text.strip())
        return m.group(1) if m else ""


@dataclass
class TaskGroup:
    """A numbered section of a change's task file, with its own tasks and edges."""

    key: str
    title: str
    order: int
    heading_line: Optional[int]
    tasks: list[Task] = field(default_factory=list)
    block: str = ""
    #: ``None`` means *no annotation was written* — which is not the same as "no
    #: dependencies", and the difference is the whole point of the fail-closed default.
    declared_depends_on: Optional[tuple[str, ...]] = None
    numbered: bool = True

    @property
    def annotated(self) -> bool:
        return self.declared_depends_on is not None

    @property
    def declared_independent(self) -> bool:
        return self.declared_depends_on == ()

    @property
    def open_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.marker == OPEN]

    @property
    def awaiting_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.marker == AWAITING]

    @property
    def is_awaiting(self) -> bool:
        return bool(self.awaiting_tasks)

    @property
    def is_complete(self) -> bool:
        """No open work and nothing awaiting a person.

        A group still holding an awaiting task is **not** complete: a dependent group must
        not start because the human question in front of it has not been answered.
        """
        return not self.open_tasks and not self.awaiting_tasks


class DependencyCycle(Exception):
    """Declared dependencies form a cycle. No group is runnable; the cycle is named."""

    def __init__(self, cycle: Sequence[str]) -> None:
        self.cycle = list(cycle)
        super().__init__("dependency cycle: " + " -> ".join(list(cycle) + [cycle[0]]))


@dataclass
class GroupPlan:
    """Every group of one change, in file order, with resolved edges."""

    groups: list[TaskGroup]
    source: Optional[Path] = None

    def by_key(self, key: str) -> Optional[TaskGroup]:
        for g in self.groups:
            if g.key == key:
                return g
        return None

    def effective_depends_on(self, group: TaskGroup) -> tuple[str, ...]:
        """The edges actually in force — the declaration, or the fail-closed serial default."""
        if group.declared_depends_on is not None:
            return group.declared_depends_on
        prior = [g for g in self.groups if g.order < group.order]
        return (prior[-1].key,) if prior else ()


# ── parsing ───────────────────────────────────────────────────────────────────────────────


def _group_heading_level(lines: Sequence[str]) -> int:
    """The heading level a project uses for groups.

    Chosen as the **shallowest level that carries at least one numbered heading**, so a file
    using `##` and one using `###` are both driven without being edited first — which is what
    `work-cycle-adoption` requires. With no numbered heading anywhere, the shallowest heading
    present is used, and failing that, level 2.
    """
    numbered: list[int] = []
    any_level: list[int] = []
    in_fence = False
    for raw in lines:
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(raw)
        if not m:
            continue
        level = len(m.group(1))
        any_level.append(level)
        if _NUMBERED_TITLE.match(m.group(2)):
            numbered.append(level)
    if numbered:
        return min(numbered)
    if any_level:
        return min(any_level)
    return 2


def _classify(line: str) -> Optional[tuple[str, str]]:
    for pattern, marker in _MARKERS:
        m = pattern.match(line)
        if m:
            return marker, m.group(1).strip()
    return None


def parse_task_groups(tasks_path: str | Path) -> GroupPlan:
    """Read a change's task file into groups, each carrying its own tasks and block.

    Every task line lands in exactly one group. Lines before the first heading become a group
    of their own rather than being discarded, and so do lines under a heading that carries no
    number — silently attaching them to the previous numbered group would inflate that group
    with work that is not its own.

    Fenced code blocks are skipped when looking for headings and annotations: a `##` inside a
    fence is content, not structure. This repository has paid for the opposite reading before.
    """
    path = Path(tasks_path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    level = _group_heading_level(lines)
    logger.debug("parse_task_groups(%s): group heading level = %d", path, level)

    groups: list[TaskGroup] = []
    preamble = TaskGroup(key="", title="(preamble)", order=0, heading_line=None, numbered=False)
    current = preamble
    block_lines: list[str] = []
    in_fence = False
    seen_keys: dict[str, int] = {}

    def _flush() -> None:
        current.block = "\n".join(block_lines).strip("\n")

    for idx, raw in enumerate(lines, start=1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            block_lines.append(raw)
            continue

        heading = None if in_fence else _HEADING.match(raw)
        if heading and len(heading.group(1)) == level:
            _flush()
            if current is preamble:
                # A preamble is a group only when it carries **task lines**. Prose before the
                # first heading — a title, an intro — is not work, and emitting it as a group
                # would shift every real group's order by one. The requirement is about task
                # lines being discarded, not about prose being preserved.
                if current.tasks:
                    groups.append(current)
            else:
                groups.append(current)

            title_raw = heading.group(2)
            numbered_m = _NUMBERED_TITLE.match(title_raw)
            if numbered_m:
                key, title, numbered = numbered_m.group(1), numbered_m.group(2), True
            else:
                key, title, numbered = _slug(title_raw), title_raw, False
            # Two groups may not share a key; a duplicate would make an edge ambiguous.
            if key in seen_keys:
                seen_keys[key] += 1
                key = f"{key}#{seen_keys[key]}"
                logger.warning(
                    "parse_task_groups(%s): duplicate group key at line %d, disambiguated to %r",
                    path, idx, key,
                )
            else:
                seen_keys[key] = 1

            current = TaskGroup(
                key=key, title=title, order=len(groups),
                heading_line=idx, numbered=numbered,
            )
            block_lines = [raw]
            continue

        block_lines.append(raw)

        if not in_fence:
            dep = _DEPENDS.search(raw)
            if dep:
                current.declared_depends_on = _parse_depends(dep.group(1))

            classified = _classify(raw)
            if classified:
                marker, body = classified
                current.tasks.append(Task(marker=marker, text=body, line_no=idx, raw=raw))

    _flush()
    if current is not preamble or current.tasks:
        groups.append(current)

    plan = GroupPlan(groups=groups, source=path)
    logger.info(
        "parse_task_groups(%s): %d groups, %d tasks (%d open, %d awaiting)",
        path, len(groups), sum(len(g.tasks) for g in groups),
        sum(len(g.open_tasks) for g in groups), sum(len(g.awaiting_tasks) for g in groups),
    )
    return plan


def _parse_depends(body: str) -> tuple[str, ...]:
    """`"none"` → `()`, an explicit declaration of independence. Otherwise the listed keys."""
    parts = [p.strip() for p in re.split(r"[,\s]+", body) if p.strip()]
    if not parts or all(p.lower() in _INDEPENDENT_WORDS for p in parts):
        return ()
    return tuple(p for p in parts if p.lower() not in _INDEPENDENT_WORDS)


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return s or "section"


# ── ordering and selection ────────────────────────────────────────────────────────────────


def _detect_cycle(plan: GroupPlan) -> Optional[list[str]]:
    """A cycle among *declared* edges, returned as the list of keys forming it."""
    state: dict[str, int] = {}  # 0 unvisited, 1 on stack, 2 done
    stack: list[str] = []

    def visit(key: str) -> Optional[list[str]]:
        if state.get(key, 0) == 2:
            return None
        if state.get(key, 0) == 1:
            return stack[stack.index(key):]
        g = plan.by_key(key)
        if g is None:
            state[key] = 2
            return None
        state[key] = 1
        stack.append(key)
        for dep in plan.effective_depends_on(g):
            found = visit(dep)
            if found:
                return found
        stack.pop()
        state[key] = 2
        return None

    for g in plan.groups:
        found = visit(g.key)
        if found:
            return found
    return None


def select_next_group(plan: GroupPlan) -> tuple[Optional[TaskGroup], dict[str, str]]:
    """The next runnable group, and a reason for every group that is not it.

    Deterministic: the lowest-ordered group with open tasks whose dependencies are complete
    and which is not itself awaiting an answer. The same file always yields the same choice.

    A group awaiting an answer is **skipped, not blocked behind** — a later group that does
    not depend on it stays runnable, which is what keeps one open question from stalling a
    whole change.

    Raises `DependencyCycle` rather than picking an order, because an arbitrary order is a
    guess that looks like a decision.
    """
    cycle = _detect_cycle(plan)
    if cycle:
        logger.error("select_next_group: dependency cycle %s — no group is runnable", cycle)
        raise DependencyCycle(cycle)

    reasons: dict[str, str] = {}
    chosen: Optional[TaskGroup] = None

    for g in sorted(plan.groups, key=lambda x: x.order):
        if not g.open_tasks:
            reasons[g.key] = "complete" if g.is_complete else "awaiting an answer"
            if g.is_awaiting:
                reasons[g.key] = (
                    f"awaiting an answer ({len(g.awaiting_tasks)} task(s))"
                )
            continue
        if g.is_awaiting:
            reasons[g.key] = (
                f"awaiting an answer ({len(g.awaiting_tasks)} task(s)), "
                f"{len(g.open_tasks)} open task(s) held behind it"
            )
            continue
        unmet = [
            dep for dep in plan.effective_depends_on(g)
            if (d := plan.by_key(dep)) is not None and not d.is_complete
        ]
        if unmet:
            how = "declared" if g.annotated else "serial default (no annotation)"
            reasons[g.key] = f"blocked by {', '.join(unmet)} [{how}]"
            continue
        if chosen is None:
            chosen = g
            reasons[g.key] = "runnable — selected"
        else:
            reasons[g.key] = "runnable — not selected (a lower-ordered group won)"

    if chosen is None:
        logger.info("select_next_group: nothing runnable; reasons=%s", reasons)
    else:
        logger.info(
            "select_next_group: %r selected (%d open tasks)", chosen.key, len(chosen.open_tasks)
        )
    return chosen, reasons


# ── slice, carry-over, reading list ───────────────────────────────────────────────────────


@dataclass
class RunNote:
    """What one finished run left behind for the next one.

    Storage is the engine's business, not the resolver's: this is passed *in*.
    """

    group_key: str
    notes: str
    finished_at: str = ""  # ISO 8601; compared lexically, which is why ISO is required
    run_id: str = ""


@dataclass
class Slice:
    """What one run receives: its own group's block, and nothing else's."""

    group_key: str
    title: str
    block: str
    tasks: list[Task]
    truncated: bool = False


def cut_slice(group: TaskGroup, limit: Optional[int] = None) -> Slice:
    """The group's block, optionally cut to at most `limit` open tasks within the group.

    The full task file is never handed over — that is the difference this whole engine exists
    to make.
    """
    if limit is None or limit >= len(group.open_tasks):
        return Slice(
            group_key=group.key, title=group.title, block=group.block,
            tasks=list(group.tasks), truncated=False,
        )
    if limit < 0:
        raise ValueError(f"task limit must not be negative: {limit}")

    keep = {id(t) for t in group.open_tasks[:limit]}
    kept: list[Task] = []
    dropped_lines: set[int] = set()
    for t in group.tasks:
        if t.marker == OPEN and id(t) not in keep:
            dropped_lines.add(t.line_no)
            continue
        kept.append(t)

    block = "\n".join(
        line for n, line in _numbered_block_lines(group) if n not in dropped_lines
    )
    logger.info(
        "cut_slice(%s): limited to %d of %d open tasks", group.key, limit, len(group.open_tasks)
    )
    return Slice(
        group_key=group.key, title=group.title, block=block, tasks=kept, truncated=True,
    )


def _numbered_block_lines(group: TaskGroup) -> list[tuple[int, str]]:
    """The group's block lines paired with their line numbers in the source file."""
    if group.heading_line is None:
        start = group.tasks[0].line_no if group.tasks else 1
        # A preamble's block starts at line 1.
        start = 1
    else:
        start = group.heading_line
    return [(start + i, line) for i, line in enumerate(group.block.splitlines())]


def carry_over_for(
    plan: GroupPlan, group: TaskGroup, notes: Iterable[RunNote],
) -> list[RunNote]:
    """The notes that travel with a slice: most recent for this group, and for its predecessor.

    Two carriers, because a fresh context forgets a discovery as readily as it forgets noise —
    a group resumed after a `PARTIAL` needs its own last run, and a group starting fresh needs
    what the group before it found out. Older runs are dropped: the point is the latest state,
    not a history.
    """
    prior = [g for g in plan.groups if g.order < group.order]
    predecessor = prior[-1] if prior else None
    wanted = {group.key} | ({predecessor.key} if predecessor else set())

    latest: dict[str, RunNote] = {}
    for note in notes:
        if note.group_key not in wanted:
            continue
        held = latest.get(note.group_key)
        if held is None or (note.finished_at, note.run_id) > (held.finished_at, held.run_id):
            latest[note.group_key] = note

    out = [latest[k] for k in (group.key, predecessor.key if predecessor else None) if k in latest]
    logger.debug(
        "carry_over_for(%s): %d note(s) from %s", group.key, len(out), [n.group_key for n in out]
    )
    return out


def reading_list(change_dir: str | Path, tasks_filename: str = "tasks.md") -> list[Path]:
    """Every markdown artifact in the change's directory except the task file.

    Recursive, because a change's specs live in subdirectories and a run that cannot read them
    is working blind. Artifacts written by *earlier runs of the same change* are included by
    construction — the list is read from disk at the moment the slice is cut, not from a
    manifest written when the change was planned.
    """
    root = Path(change_dir)
    if not root.is_dir():
        logger.warning("reading_list(%s): not a directory", root)
        return []
    out = sorted(
        p for p in root.rglob("*.md")
        if p.is_file() and not (p.parent == root and p.name == tasks_filename)
    )
    logger.debug("reading_list(%s): %d artifact(s)", root, len(out))
    return out
