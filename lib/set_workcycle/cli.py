"""One way into the engine: a command run from the project's own tree.

There is exactly **one** entry point, and every caller uses it — the agent working in the
project, and the framework's surface alike. That is not tidiness: a second way to start a
unit is a second producer of run state, and two producers of one state is a disagreement
waiting to be discovered by whoever reads it.

The command needs **no running framework service and no network access to the framework**.
An agent in a project's tree types it; the framework's surface shells out to the same thing.
What the surface's own job is, is *reading* the state this writes.

**Answer intake runs on every path**, including the paths that only report. That is stated
as a requirement because the opposite was measured: in the proven engine the correct intake
existed but lived in the rarely-called command variant, so questions went unanswered while
the code that answered them was right there. A behaviour that only some entry points have
is, statistically, a behaviour the system does not have. Here it is structural rather than
remembered — every path opens the engine through `_open()`, and `_open()` takes in answers.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from .adoption import ADOPTION_REL, read_adoption
from .connector import awaiting_tasks, intake, write_answer
from .engine import RUN_STATE_DIR, UnitKind, WorkUnit
from .groups import DependencyCycle, parse_task_groups, select_next_group
from .lock import LockHeld, SeatRefused, acquire, read_lock, validate_seat

logger = logging.getLogger(__name__)

__all__ = ["main", "build_parser", "EngineView", "open_engine", "read_run_state"]

@dataclass
class EngineView:
    """Everything a command needs, after answers have been taken in.

    Constructed by `_open()` and by nothing else. That is what makes intake structural: a
    path that skips intake would have to skip getting the state it is reporting on.
    """

    tree: Path
    change: str
    intake_lines: list[str]
    plan: Optional[object] = None
    tasks_path: Optional[Path] = None
    adopted: bool = True
    missing: str = ""
    adoption: Optional[object] = None


def _awaiting_keys(tree: Path, change: str, tasks_path: Optional[Path]) -> set[str]:
    if tasks_path is None or not tasks_path.is_file():
        return set()
    return {f"{change}#{task}" for task, _ in awaiting_tasks(tasks_path)}


def open_engine(tree: str | Path, change: str = "", changes_dir: str = "") -> EngineView:
    """Open the engine against a tree — **taking in pending answers first, on every path**."""
    root = Path(tree)
    tasks_path: Optional[Path] = None
    plan = None
    adopted = True
    missing = ""

    # Where a project keeps its changes comes from the project's own declaration. Defaulting
    # to a convention here would be the guessed default `work-cycle-adoption` refuses: a
    # guess that happens to be right for this repository is indistinguishable, from the
    # outside, from a project that actually said so.
    adoption = read_adoption(root, changes_dir_override=changes_dir)
    if not adoption.adopted:
        return EngineView(tree=root, change=change, intake_lines=intake(root).as_lines(),
                          adopted=False, missing=adoption.missing)

    base = root / adoption.changes_dir
    if not base.is_dir():
        adopted, missing = False, (
            f"{adoption.changes_dir} — declared in {ADOPTION_REL}, but there is no such "
            f"directory in this tree"
        )
    elif change:
        candidate = base / change / "tasks.md"
        if candidate.is_file():
            tasks_path = candidate
        else:
            adopted, missing = False, f"no task file for change {change!r} at {candidate}"

    result = intake(root, awaiting=_awaiting_keys(root, change, tasks_path))
    if tasks_path is not None:
        plan = parse_task_groups(tasks_path)

    return EngineView(
        tree=root, change=change, intake_lines=result.as_lines(),
        plan=plan, tasks_path=tasks_path, adopted=adopted, missing=missing,
        adoption=adoption,
    )


def read_run_state(tree: str | Path, change: str = "") -> list[dict]:
    """Every recorded run, read straight off disk — no process started, none required.

    A stale claim is distinguishable from a live one here rather than by the caller: the
    record carries the pid it was written by, and whether that pid is alive is a question the
    reader can answer for itself. A record that merely *exists* proves nothing about a run.
    """
    root = Path(tree) / RUN_STATE_DIR
    if change:
        root = root / change
    if not root.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("unreadable run record %s: %s", path, exc)
            continue
        data["_path"] = str(path)
        data["_status"] = _run_status(data)
        out.append(data)
    return out


def _run_status(record: dict) -> str:
    """`"finished"`, `"running"` or `"stale"` — three states, and the third is not silence."""
    if record.get("commit") is not None or record.get("set_aside") is not None:
        return "finished"
    pid = int(record.get("pid") or 0)
    if pid <= 0:
        return "stale"
    import os

    try:
        os.kill(pid, 0)
        return "running"
    except ProcessLookupError:
        return "stale"
    except PermissionError:
        return "running"


# ── commands ──────────────────────────────────────────────────────────────────────────────


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for line in payload.get("lines", []):
        print(line)


def cmd_status(args) -> int:
    """Report what is runnable and where runs have got to. Takes in answers like every path."""
    view = open_engine(args.tree, args.change, args.changes_dir)
    lines = [f"answers: {l}" for l in view.intake_lines]

    if not view.adopted:
        # Never rendered as "nothing to do". An un-adopted project and a finished one are
        # different states, and a reader must not be able to take the first for the second.
        lines.append(f"NOT ADOPTED: {view.missing}")
        _emit({"adopted": False, "missing": view.missing, "lines": lines}, args.json)
        return 2

    lock = read_lock(args.tree)
    if lock is not None:
        lines.append(f"lock: {lock.status} — held by {lock.seat} (pid {lock.pid})")

    reasons: dict = {}
    selected = None
    if view.plan is not None:
        try:
            group, reasons = select_next_group(view.plan)
            selected = group.key if group else None
        except DependencyCycle as exc:
            lines.append(f"dependency cycle: {' -> '.join(exc.cycle)} — no group is runnable")
            _emit({"adopted": True, "cycle": exc.cycle, "lines": lines}, args.json)
            return 3
        lines.append(f"next runnable group: {selected}" if selected
                     else "nothing runnable — reasons per group:")
        for key, why in reasons.items():
            lines.append(f"  {key}: {why}")

    runs = read_run_state(args.tree, args.change)
    for r in runs:
        lines.append(f"run {r.get('unit_id')}: {r['_status']}")

    _emit({"adopted": True, "selected": selected, "reasons": reasons,
           "runs": [{"unit_id": r.get("unit_id"), "status": r["_status"]} for r in runs],
           "lines": lines}, args.json)
    return 0


def cmd_run(args) -> int:
    """Start one work unit against this tree."""
    view = open_engine(args.tree, args.change, args.changes_dir)
    lines = [f"answers: {l}" for l in view.intake_lines]

    if not view.adopted:
        lines.append(f"NOT ADOPTED: {view.missing}")
        _emit({"adopted": False, "missing": view.missing, "lines": lines}, args.json)
        return 2

    try:
        validate_seat(args.seat)
    except SeatRefused as exc:
        lines.append(f"seat refused: {exc}")
        _emit({"started": False, "lines": lines}, args.json)
        return 4

    try:
        group, reasons = select_next_group(view.plan) if view.plan else (None, {})
    except DependencyCycle as exc:
        lines.append(f"dependency cycle: {' -> '.join(exc.cycle)} — no group is runnable")
        _emit({"started": False, "cycle": exc.cycle, "lines": lines}, args.json)
        return 3

    if group is None:
        lines.append("nothing runnable — reasons per group:")
        for key, why in reasons.items():
            lines.append(f"  {key}: {why}")
        _emit({"started": False, "reasons": reasons, "lines": lines}, args.json)
        return 1

    try:
        state = acquire(args.tree, args.seat, change=args.change, group=group.key)
    except LockHeld as exc:
        lines.append(
            f"refused: {exc.state.seat} holds this tree's lock "
            f"(pid {exc.state.pid}, {exc.state.status})"
        )
        _emit({"started": False, "holder": exc.state.seat, "lines": lines}, args.json)
        return 5

    unit = WorkUnit(change=args.change, tree=Path(args.tree), seat=state.seat,
                    kind=UnitKind.SLICE, group_key=group.key)
    lines.append(f"started {unit.unit_id} on group {group.key} (seat {state.seat})")
    _emit({"started": True, "unit_id": unit.unit_id, "group": group.key,
           "started_by": args.started_by, "lines": lines}, args.json)
    return 0


def cmd_answer(args) -> int:
    """Place an answer in the connector. Any caller may; the engine never learns who."""
    path = write_answer(args.tree, args.change, args.task, args.answer, source=args.source)
    _emit({"written": str(path), "lines": [f"answer written: {path}"]}, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="set-work-cycle",
        description="Run a change one task group at a time, in the project's own tree.",
    )
    parser.add_argument("--tree", default=".", help="the working tree to operate on")
    parser.add_argument("--change", default="", help="the change to drive")
    parser.add_argument("--changes-dir", default="", help="override where changes live")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    # Exactly ONE subcommand starts a unit. `test_only_one_interface_starts_a_work_unit`
    # fails if a second appears.
    run = sub.add_parser("run", help="start one work unit (the only start path)")
    run.add_argument("--seat", required=True,
                     help="the agent session this unit belongs to; a project name is refused")
    run.add_argument("--started-by", default="agent",
                     help="who invoked the command — recorded, never a second start path")
    run.set_defaults(func=cmd_run, starts_a_unit=True)

    status = sub.add_parser("status", help="report what is runnable and where runs got to")
    status.set_defaults(func=cmd_status, starts_a_unit=False)

    answer = sub.add_parser("answer", help="place an answer for an awaiting task")
    answer.add_argument("--task", required=True)
    answer.add_argument("--answer", required=True)
    answer.add_argument("--source", required=True, help="who is answering")
    answer.set_defaults(func=cmd_answer, starts_a_unit=False)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
