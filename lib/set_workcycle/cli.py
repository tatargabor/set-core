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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .adoption import ADOPTION_REL, read_adoption
from .connector import (
    ResumeCondition,
    answers_for,
    awaiting_tasks,
    clear_awaiting,
    intake,
    mark_awaiting,
    record_answer,
    write_answer,
)
from .engine import (
    RUN_STATE_DIR,
    UnitKind,
    UnitRecord,
    WorkUnit,
    changed_files,
    commit_unit,
    resolve_gate_steps,
    run_gate,
)
from .groups import DependencyCycle, RunNote, carry_over_for, cut_slice, parse_task_groups, \
    reading_list, select_next_group
from .lock import LockHeld, SeatRefused, acquire, read_lock, release, validate_seat
from .prompt import build_unit_prompt
from .runner import run_agent_session

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
    #: `(task, answer)` for every question released by this intake. Carried into the unit's
    #: prompt: an answer nobody tells the next run about is an answer nobody acted on.
    answers: list = field(default_factory=list)


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

    # An answer that is merely *recorded* leaves its task marked as awaiting forever, so the
    # group it belongs to never becomes runnable again and the answer has changed nothing.
    # Releasing is what makes intake mean something — and it happens here, on every path,
    # for the same reason intake does.
    answers: list[tuple[str, str]] = []
    if tasks_path is not None:
        for applied in result.applied:
            if clear_awaiting(tasks_path, applied.task):
                answers.append((applied.task, applied.answer))
                record_answer(root, change, applied.task, applied.answer, applied.source)
                logger.info("released %s — an answer arrived from %s",
                            applied.key, applied.source or "an unnamed source")
        plan = parse_task_groups(tasks_path)

    return EngineView(
        tree=root, change=change, intake_lines=result.as_lines(),
        plan=plan, tasks_path=tasks_path, adopted=adopted, missing=missing,
        adoption=adoption, answers=answers,
    )


def gate_failed_groups(tree: str | Path, change: str = "") -> set[str]:
    """Groups whose LAST recorded run ended on a red gate.

    Read off the run records, because the group plan is parsed from a task file and a task
    file cannot know what a gate did. One record per unit means the record IS the latest run
    for that group; a later green run overwrites it and the group clears itself.
    """
    failed: set[str] = set()
    for rec in read_run_state(tree, change):
        state = (rec.get("gate") or {}).get("state")
        key = str(rec.get("group") or "")
        if not key:
            continue
        if state == "failed":
            failed.add(key)
        else:
            failed.discard(key)
    if failed:
        logger.info("groups held by a failed gate in %s: %s", tree, sorted(failed))
    return failed


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
            group, reasons = select_next_group(
                view.plan, gate_failed=gate_failed_groups(view.tree, args.change))
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
        group, reasons = (
            select_next_group(view.plan,
                              gate_failed=gate_failed_groups(view.tree, args.change))
            if view.plan else (None, {}))
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

    try:
        record = _drive(unit, view, group, args, lines)
    finally:
        release(args.tree, state.seat)

    _emit({
        "started": True, "unit_id": unit.unit_id, "group": group.key,
        "started_by": args.started_by,
        "outcome": record.verdict.outcome.value if record.verdict else "FAILED_TO_REPORT",
        "gate": None if record.gate is None else record.gate.state,
        "committed": bool(record.commit and record.commit.committed),
        "set_aside": record.set_aside_condition,
        "record": str(record.path()),
        "lines": lines,
    }, args.json)
    return 0 if record.verdict else 6


def _run_notes(tree, change: str) -> list:
    """Carry-over material, read from the run records earlier units left behind."""
    notes = []
    for r in read_run_state(tree, change):
        verdict = r.get("verdict") or {}
        text = (verdict.get("notes") or "").strip() or (verdict.get("summary") or "").strip()
        if r.get("group") and text:
            notes.append(RunNote(group_key=str(r["group"]), notes=text,
                                 finished_at=str(r.get("verdict_at") or ""),
                                 run_id=str(r.get("unit_id") or "")))
    return notes


def _drive(unit, view, group, args, lines: list) -> UnitRecord:
    """One unit, all the way through — and in the order the specs fix.

    The verdict is recorded BEFORE the gate runs, so a process that dies between them leaves
    a started unit with no completion rather than a unit that looks never attempted while its
    work sits in the tree.
    """
    import os
    import time

    change_dir = Path(view.tasks_path).parent
    slice_ = cut_slice(group, limit=args.limit)
    artifacts = [str(p.relative_to(view.tree)) for p in reading_list(change_dir)]
    carried = carry_over_for(view.plan, group, _run_notes(view.tree, args.change))

    record = UnitRecord(unit=unit, started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        pid=os.getpid())
    record.save()

    marked_before = [t.key for t in group.tasks if t.marker == "done"]
    baseline = _head(view.tree)

    prompt = build_unit_prompt(
        args.change, slice_, reading_list=artifacts, carry_over=carried,
        tasks_path=str(Path(view.tasks_path).relative_to(view.tree)),
        answers=answers_for(view.tree, args.change, [t.key for t in group.tasks]),
    )
    if args.dry_run:
        lines.append(f"dry run: prompt built ({len(prompt)} chars); no session started")
        return record

    agent = _AGENT_RUNNER or run_agent_session
    run = agent(prompt, view.tree, model=args.model or None)
    lines.append(f"agent session {run.session_id or '(none)'} ended (exit {run.exit_code})")

    from .verdict import VerdictSchemaError, extract_verdict

    try:
        verdict = extract_verdict(run.final_text)
    except VerdictSchemaError as exc:
        # A reporting failure, never an inferred outcome: guessing PARTIAL here would produce
        # a state the engine could act on, which is exactly the problem.
        lines.append(f"the unit failed to report a verdict: {exc}")
        record.save()
        return record

    record.record_verdict(verdict)            # BEFORE the gate — the ordering is a requirement
    lines.append(f"verdict: {verdict.outcome.value} — {verdict.summary}")

    plan_now = parse_task_groups(view.tasks_path)
    group_now = plan_now.by_key(group.key)
    marked_now = [t.key for t in (group_now.tasks if group_now else []) if t.marker == "done"]
    diff = record.check_against_tree(marked_now, before=marked_before)
    lines.extend(f"  {l}" for l in diff.as_lines())

    if verdict.stops:
        for decision in verdict.open_decisions:
            if decision.task:
                mark_awaiting(view.tasks_path, decision.task, decision.question)
                lines.append(f"  marked {decision.task} as awaiting a person")
        first = verdict.open_decisions[0]
        record.set_aside(ResumeCondition.human_decision(first.question, first.task).to_dict())
        lines.append("set aside: a person must answer before this group continues")
        return record

    steps = resolve_gate_steps(_change_stub(args.change), _profile_for(view), view.tree,
                               adoption=view.adoption)
    gate = run_gate(steps, view.tree, unit_files=changed_files(view.tree, baseline))
    record.gate = gate
    record.save()
    lines.append(f"gate: {gate.state} — {gate.detail}")
    if gate.attribution:
        lines.append(f"  attribution: {gate.attribution}")

    record.commit = commit_unit(unit, gate, baseline=baseline)
    record.save()
    lines.append(
        f"commit: {record.commit.sha[:12]}" if record.commit.committed
        else f"no commit — {record.commit.reason}"
    )
    return record


def _head(tree) -> str:
    import subprocess

    try:
        out = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except OSError:
        return ""


def _change_stub(name: str):
    """A minimal change object for the gate-configuration chain, which expects one."""
    from set_orch.state import Change

    return Change(name=name)


def _profile_for(view):
    """The project's resolved profile — where everything project-specific comes from."""
    try:
        from set_orch.profile_loader import load_profile

        return load_profile(str(view.tree))
    except Exception:
        logger.info("no profile resolved for %s — the engine supplies none", view.tree)
        return None


#: Injected by tests so the lifecycle can be driven without spawning an agent. Production
#: leaves it None, so there is no second start path hiding here.
_AGENT_RUNNER = None


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
    run.add_argument("--limit", type=int, default=None,
                     help="cut the slice to at most N open tasks within the group")
    run.add_argument("--model", default="", help="model for the unit's agent session")
    run.add_argument("--dry-run", action="store_true",
                     help="build the slice and the prompt, start no session")
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
