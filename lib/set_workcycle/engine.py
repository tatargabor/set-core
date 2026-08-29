"""The work-unit lifecycle: run, verdict, gate, commit — or set aside with a condition.

A **work unit** is a slice of work run in a fresh agent context and closed by a verdict, then
a gate, then a commit. The engine owns that lifecycle and nothing else. *What one unit is*
belongs to the lane: a task group (slice lane), one phase of an item (phase lane), one
viewpoint on a phase (lens lane). The kind is an **attribute** of the unit, which is why the
lanes this change does not ship add unit kinds rather than a second engine.

Two orderings here are load-bearing and neither is obvious:

- **The verdict is written before the gate runs.** A run killed between the two would
  otherwise look like a unit that was never attempted, and the work sitting in the tree would
  have no owner.
- **The commit happens only behind a green gate**, and "no gate ran" is recorded as its own
  state. A project that declares no gate steps runs with none — never with a guessed default —
  and the record says so, because a section gate is weaker than a merge gate and must not read
  as the same assurance.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from .verdict import Outcome, TreeDiff, Verdict, diff_against_tree

logger = logging.getLogger(__name__)

__all__ = [
    "RUN_STATE_DIR",
    "UnitKind",
    "WorkUnit",
    "GateOutcome",
    "CommitOutcome",
    "UnitRecord",
    "progress_from_markers",
    "resolve_gate_steps",
    "run_gate",
    "attribute_failure",
    "commit_unit",
    "changed_files",
]

#: Runtime state, not an install artifact.
RUN_STATE_DIR = "set/runtime/work-cycle"


class UnitKind(str, Enum):
    """What one unit *is*. An attribute, deliberately — not a subclass and not a second engine.

    Only `SLICE` is driven by this change. The other two are declared because the abstraction
    was designed to carry them: if admitting the fix lane required changing this enum's
    meaning, that would be a design error rather than a future task.
    """

    SLICE = "slice"
    PHASE = "phase"
    LENS = "lens"


@dataclass
class WorkUnit:
    """One piece of work, its tree, its seat, and what it was given to work from."""

    change: str
    tree: Path
    seat: str
    kind: UnitKind = UnitKind.SLICE
    group_key: str = ""
    work: str = ""                       # the slice — this group's block, never the whole file
    carry_over: tuple[str, ...] = ()
    reading_list: tuple[str, ...] = ()
    #: A unit's input MAY be other units' verdicts (the lens lane's comparison). Preserved in
    #: full when the unit is set aside — see `UnitRecord.set_aside`.
    inputs: tuple[Verdict, ...] = ()
    lens: str = ""
    unit_id: str = ""

    def __post_init__(self) -> None:
        self.tree = Path(self.tree)
        if not self.unit_id:
            self.unit_id = f"{self.change}--{self.group_key or self.kind.value}"


# ── progress ──────────────────────────────────────────────────────────────────────────────


def progress_from_markers(done: int, total: int) -> dict:
    """Progress, derived from completed task markers and from nothing else.

    Never from turns, events, elapsed time or messages exchanged. An activity counter rises
    while a unit is stuck as readily as while it is working, so reporting it as progress is
    reporting the opposite of what the reader is asking about.
    """
    pct = round(done / total * 100.0, 1) if total else 0.0
    return {"done": done, "total": total, "percent": pct, "derived_from": "task markers"}


# ── the gate ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateStep:
    """One resolved gate: its name and the command the profile supplies for it."""

    name: str
    command: str


@dataclass
class GateOutcome:
    """What the gate did — including the case where there was none."""

    steps: tuple[GateStep, ...] = ()
    failures: tuple[str, ...] = ()
    #: `"no-gate"` | `"passed"` | `"failed"`. Three states, never two: a project that declares
    #: no gate has not passed one, and a record that says "passed" for it would claim an
    #: assurance nobody produced.
    state: str = "no-gate"
    attribution: str = ""   # "this-unit" | "elsewhere" | "undetermined" | ""
    detail: str = ""
    outputs: dict = field(default_factory=dict)

    @property
    def ran(self) -> bool:
        return self.state != "no-gate"

    @property
    def passed(self) -> bool:
        return self.state == "passed"

    @property
    def blocks_commit(self) -> bool:
        return self.state == "failed"


def _declared_gate_steps(adoption: Any, tree: str | Path) -> list[GateStep]:
    """The project declared the key, so the project decides — including deciding *none*.

    Declaring the key empty is an answer, not a gap, and the engine must not answer it a
    second time. Falling back to profile detection here would give a project that
    deliberately narrowed its gate a wider one it never asked for, and the green result
    would be indistinguishable from its own gate having run. The declaration therefore wins
    outright: nothing below reads the profile.

    Names are made unique because `GateOutcome.outputs` is keyed on them — two identical
    declared commands must not silently collapse into one recorded output.
    """
    steps: list[GateStep] = []
    seen: dict[str, int] = {}
    for command in adoption.gates:
        command = str(command).strip()
        if not command:
            continue
        n = seen.get(command, 0) + 1
        seen[command] = n
        steps.append(GateStep(name=command if n == 1 else f"{command} ({n})", command=command))
    logger.info("gate steps declared by the project at %s: %d step(s)", tree, len(steps))
    return steps


def resolve_gate_steps(change: Any, profile: Any, tree: str | Path,
                       directives: Optional[dict] = None,
                       adoption: Any = None) -> list[GateStep]:
    """The project's own declaration first; failing that, gate names from the existing
    resolution chain and commands from the project's profile.

    The engine contributes no gate definitions and no commands. `resolve_gate_config` is the
    same six-layer chain the merge path uses, so there is exactly one source of gate
    configuration — which is the one thing the design fixed in advance.

    Measured (task 2.1): the existing `GatePipeline` cannot also *run* these without writing
    orchestration state — its failure path sets the whole change's `status` to `failed`, which
    for one section's red is an untrue statement about the change. So the configuration is
    reused and the running is not.
    """
    if adoption is not None and getattr(adoption, "gates_declared", False):
        return _declared_gate_steps(adoption, tree)

    from set_orch.gate_profiles import resolve_gate_config

    gc = resolve_gate_config(change, profile, directives, tree)
    detectors = {
        "build": "detect_build_command",
        "test": "detect_test_command",
        "e2e": "detect_e2e_command",
    }
    steps: list[GateStep] = []
    for name in sorted(gc.gate_names()):
        if not gc.should_run(name):
            continue
        detector = detectors.get(name)
        command = ""
        if detector and profile is not None and hasattr(profile, detector):
            try:
                command = getattr(profile, detector)(str(tree)) or ""
            except Exception:
                logger.warning("profile.%s threw for %s", detector, tree, exc_info=True)
                command = ""
        if command:
            steps.append(GateStep(name=name, command=command))
        else:
            logger.debug("gate %r has no command from this profile — not a step", name)
    logger.info("resolved %d gate step(s) for %s: %s", len(steps), tree, [s.name for s in steps])
    return steps


def run_gate(
    steps: Sequence[GateStep], tree: str | Path, *, unit_files: Optional[Iterable[str]] = None,
    timeout: Optional[float] = None, runner=None,
) -> GateOutcome:
    """Run the resolved steps. No steps means **no gate**, not a passed one."""
    if not steps:
        logger.info("no gate steps declared for %s — running with no gate", tree)
        return GateOutcome(state="no-gate",
                           detail="the project declares no gate steps; no gate was run")

    exec_step = runner or _run_step
    failures: list[str] = []
    outputs: dict[str, str] = {}
    for step in steps:
        code, output = exec_step(step, tree, timeout)
        outputs[step.name] = output
        if code != 0:
            failures.append(step.name)
            logger.error("gate step %r failed (exit %s) in %s", step.name, code, tree)
            break  # a section gate stops at the first failure; the work stays in the tree

    if not failures:
        return GateOutcome(steps=tuple(steps), state="passed", outputs=outputs,
                           detail=f"{len(steps)} step(s) passed")

    attribution, detail = attribute_failure(
        implicated=_implicated_files(outputs.get(failures[0], ""), tree),
        unit_files=unit_files,
    )
    return GateOutcome(
        steps=tuple(steps), failures=tuple(failures), state="failed",
        attribution=attribution, detail=detail, outputs=outputs,
    )


def _run_step(step: GateStep, tree: str | Path, timeout: Optional[float]) -> tuple[int, str]:
    proc = subprocess.run(
        step.command, shell=True, cwd=str(tree), capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _implicated_files(output: str, tree: str | Path) -> Optional[set[str]]:
    """Files a failure names, or `None` when none can be established.

    `None` is a real answer here, not a fallback: it is what "cannot be determined" is made
    of, and it is what stops the engine from blaming the unit by default.
    """
    if not output:
        return None
    root = Path(tree)
    found: set[str] = set()
    for token in output.replace("(", " ").replace(")", " ").replace(":", " ").split():
        cleaned = token.strip("\"',[]")
        if "/" not in cleaned and "." not in cleaned:
            continue
        candidate = cleaned.lstrip("./")
        # ⚠ An empty candidate is the TREE ROOT, and `(root / "").exists()` is True — so a
        # bare `.` or `./` anywhere in the output used to enter the set as a "named file".
        # Measured on a live run: the implicated list began with `''`.
        if not candidate:
            continue
        if (root / candidate).exists():
            found.add(candidate)
    return found or None


def attribute_failure(
    implicated: Optional[Iterable[str]], unit_files: Optional[Iterable[str]],
) -> tuple[str, str]:
    """Whether a gate failure came from this unit's own work, from elsewhere, or unknown.

    A tree may hold work the engine did not do and does not control, so attributing every
    red to the unit that happened to be running is the cheapest wrong answer available — and
    it is the one that gets a person blamed for someone else's break. Where attribution
    cannot be established the engine says so; it does **not** default to the unit.
    """
    if implicated is None:
        return "undetermined", (
            "the gate output names no files, so which work this failure implicates could not "
            "be established; it is NOT attributed to this unit"
        )
    implicated_set = {str(f) for f in implicated}
    mine = {str(f) for f in (unit_files or ())}
    if not implicated_set:
        return "undetermined", "no files could be established from the gate output"
    overlap = implicated_set & mine
    if overlap:
        return "this-unit", f"the failure implicates files this unit changed: {sorted(overlap)}"
    if not mine:
        return "elsewhere", (
            "this unit changed no file in the tree, so the failure cannot be its work"
        )
    # Everything else is UNDETERMINED, not `elsewhere`. Not knowing which files a failure
    # implicates and knowing they are someone else's are different states, and only the
    # second one exonerates. Measured on a live cross-run, three reasons why the file set is
    # not a list of causes:
    #   · it is scraped from PROSE — a remediation hint naming the file to EDIT arrived as
    #     evidence about the file that BROKE;
    #   · it is scraped from the whole output, PASSING lines included — a test that ran green
    #     was listed as implicated;
    #   · the effect can be INDIRECT — the real cause was a task file this unit did change,
    #     feeding a generated artefact whose name is the only thing the failure mentions. No
    #     filename intersection can ever reach that, so a clean intersection proves nothing.
    # The direction is what makes the old answer expensive: `elsewhere` reads as "not your
    # work", which is precisely what waves a real break through.
    return "undetermined", (
        f"the gate output names files, none of which this unit changed — but that is not "
        f"evidence of innocence: the output carries prose and passing steps too, and an "
        f"effect can be indirect. NOT attributed to this unit, and not attributed elsewhere: "
        f"{sorted(implicated_set)[:5]}"
    )


def changed_files(tree: str | Path, since: str = "") -> set[str]:
    """Paths this unit touched: uncommitted changes, plus anything committed since `since`."""
    root = str(tree)
    out: set[str] = set()
    try:
        status = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                                capture_output=True, text=True, timeout=15)
        for line in status.stdout.splitlines():
            if len(line) > 3:
                out.add(line[3:].strip().split(" -> ")[-1])
        if since:
            diff = subprocess.run(["git", "-C", root, "diff", "--name-only", since, "HEAD"],
                                  capture_output=True, text=True, timeout=15)
            out.update(l.strip() for l in diff.stdout.splitlines() if l.strip())
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("changed_files(%s) failed: %s", root, exc)
        return set()
    return out


# ── the commit ────────────────────────────────────────────────────────────────────────────


@dataclass
class CommitOutcome:
    """Whether a commit happened, and — when it did not — the reason in plain terms."""

    committed: bool
    sha: str = ""
    reason: str = ""
    #: Set when the tree moved on although the ENGINE did not commit — the unit's agent
    #: committed the work itself. A field rather than a sentence in `reason`, because the
    #: thing a later reader acts on must not have to be parsed out of prose.
    committed_by_agent: str = ""


def _head_sha(tree: str | Path, runner=None) -> str:
    run = runner or _git
    code, out = run(["git", "-C", str(tree), "rev-parse", "HEAD"])
    return out.strip() if code == 0 else ""


def commit_unit(unit: WorkUnit, gate: GateOutcome, *, message: Optional[str] = None,
                runner=None, baseline: str = "") -> CommitOutcome:
    """Commit this unit's work, but only when the gate did not fail.

    On a failed gate: no commit, the work stays in the tree, and the caller does not advance.
    Leaving the work is deliberate — a unit's output is what a person needs in order to fix
    the failure, and discarding it to keep the tree tidy destroys the evidence.
    """
    if gate.blocks_commit:
        # ⚠ "The work stays in the tree" is a CLAIM about the tree, and the engine used to
        # make it without looking. Measured on a live cross-run: the agent had committed the
        # work itself before the gate ran, so the record said `committed: false` and "stays in
        # the tree" while the commit sat in the history and `git status` was clean.
        #
        # The engine cannot prevent this and must not pretend otherwise — the agent holds git,
        # so "commit only behind a green gate" is a sentence, not a constraint; what a unit
        # can do is decided by its tools. What the engine CAN do is stop reporting a tree
        # state it never measured.
        moved = _head_sha(unit.tree, runner) if baseline else ""
        if moved and moved != baseline:
            logger.error(
                "commit refused for %s (gate failed: %s) — but the tree ALREADY MOVED to %s: "
                "the unit's agent committed its own work before the gate ran",
                unit.unit_id, ", ".join(gate.failures), moved[:12],
            )
            return CommitOutcome(
                False, committed_by_agent=moved,
                reason=(f"gate failed: {', '.join(gate.failures)}; ⚠ the work is ALREADY "
                        f"COMMITTED as {moved[:12]} — its agent committed before the gate ran, "
                        f"so the tree is NOT holding it for review"),
            )
        logger.error(
            "commit refused for %s: the gate failed (%s); the work stays in the tree",
            unit.unit_id, ", ".join(gate.failures),
        )
        return CommitOutcome(False, reason=f"gate failed: {', '.join(gate.failures)}")

    run = runner or _git
    root = str(unit.tree)
    text = message or (
        f"{unit.change}: {unit.group_key or unit.kind.value}\n\n"
        f"Work unit {unit.unit_id} ({unit.kind.value}). "
        f"Gate: {gate.state}"
        + (f" ({', '.join(s.name for s in gate.steps)})" if gate.steps else "")
        + ".\n"
    )
    # ⚠ `git add -A` alone stages the ENGINE'S OWN run records into the project's history.
    # Measured live: `set/runtime/work-cycle/<change>/<unit>.json` arrived staged in a
    # consumer tree. Nothing was lost — the commit failed on an unrelated lock — but the next
    # green gate would have committed the engine's bookkeeping as if it were the project's
    # work, in the project's own repository.
    #
    # The exclusion belongs HERE rather than in the project's `.gitignore`: the directory is
    # this engine's invention, so keeping it out of someone else's history is this engine's
    # job, and a fix that requires every adopting project to add a line is a fix that will be
    # missed by the project that adopts next.
    code, _ = run(["git", "-C", root, "add", "-A", "--", ".", f":(exclude){RUN_STATE_DIR}"])
    if code != 0:
        return CommitOutcome(False, reason="git add failed")
    code, out = run(["git", "-C", root, "commit", "-m", text])
    if code != 0:
        if "nothing to commit" in out:
            return CommitOutcome(False, reason="the unit changed nothing in the tree")
        return CommitOutcome(False, reason=f"git commit failed: {out.strip()[:200]}")
    _, sha = run(["git", "-C", root, "rev-parse", "HEAD"])
    logger.info("work unit %s committed as %s (gate: %s)", unit.unit_id, sha.strip()[:12],
                gate.state)
    return CommitOutcome(True, sha=sha.strip())


def _git(argv: Sequence[str]) -> tuple[int, str]:
    proc = subprocess.run(list(argv), capture_output=True, text=True, timeout=120)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ── the durable record ────────────────────────────────────────────────────────────────────


@dataclass
class UnitRecord:
    """One unit's durable state, written where a reader can read it without running anything.

    The verdict is persisted **before** the gate. A process that dies between the two leaves a
    started unit with no completion — which is the truth — instead of a unit that looks never
    attempted while its work sits in the tree.
    """

    unit: WorkUnit
    started_at: str = ""
    verdict: Optional[Verdict] = None
    verdict_at: str = ""
    gate: Optional[GateOutcome] = None
    commit: Optional[CommitOutcome] = None
    diff: Optional[TreeDiff] = None
    set_aside_condition: Optional[dict] = None
    pid: int = 0
    #: Who asked for this run, as the caller DECLARED it. Empty means nobody said,
    #: which is a different fact from "started by an agent" and is kept as such:
    #: the flag's old default filled this in with a plausible-looking word, so a
    #: record could not distinguish a stated origin from an unstated one.
    #:
    #: ⚠ A CLAIM, never a measurement. Nothing here verifies that the named seat
    #: asked for the run, and any surface rendering it must say so — the same
    #: distinction the fleet screen already draws between a recorded parent and
    #: one found by walking the process tree.
    started_by: str = ""
    #: The agent session this run actually got, read off that session's own first
    #: event rather than generated here. Empty means the session never announced
    #: one, which is NOT the same as the run having had no session.
    session_id: str = ""
    #: What the project's declared reading paths resolved to — present, missing,
    #: refused. `None` where the project declared none. A dropped path that leaves
    #: no trace is indistinguishable from one that was never declared.
    reading: Optional[dict] = None

    def path(self) -> Path:
        return Path(self.unit.tree) / RUN_STATE_DIR / self.unit.change / f"{self.unit.unit_id}.json"

    def stream_path(self) -> Path:
        """Beside the record, under the tree the engine was GIVEN.

        Derived from `self.unit.tree` and nothing else — no framework path, no
        home directory, no temp dir. The stream carries the project's domain, so
        where it lands is a confidentiality decision (see the module the record
        lives in) rather than a storage one.
        """
        return self.path().with_suffix(".stream.jsonl")

    def to_dict(self) -> dict:
        return {
            "unit_id": self.unit.unit_id,
            "change": self.unit.change,
            "group": self.unit.group_key,
            "kind": self.unit.kind.value,
            "lens": self.unit.lens,
            "seat": self.unit.seat,
            "pid": self.pid,
            # Absence is a value here, and it is spelled out rather than left to
            # a reader's default: `None` says nobody declared / nothing announced,
            # and a reader that turns it into a word has invented a fact.
            "started_by": self.started_by or None,
            "started_by_is_claim": True,
            "session_id": self.session_id or None,
            "reading": self.reading,
            "started_at": self.started_at,
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "verdict_at": self.verdict_at,
            "gate": None if self.gate is None else {
                "state": self.gate.state,
                "steps": [s.name for s in self.gate.steps],
                "failures": list(self.gate.failures),
                "attribution": self.gate.attribution,
                "detail": self.gate.detail,
            },
            "commit": None if self.commit is None else {
                "committed": self.commit.committed,
                "sha": self.commit.sha,
                "reason": self.commit.reason,
                "committed_by_agent": self.commit.committed_by_agent,
            },
            "diff": None if self.diff is None else {
                "claimed_but_unmarked": list(self.diff.claimed_but_unmarked),
                "marked_but_unclaimed": list(self.diff.marked_but_unclaimed),
                "claimed_but_done_earlier": list(self.diff.claimed_but_done_earlier),
            },
            "set_aside": self.set_aside_condition,
            # Every input verdict, in full. A unit whose input is other units' verdicts is
            # set aside precisely when they diverge, and what a reader needs at that moment
            # is WHERE they diverged — which a summary has already thrown away.
            "inputs": [v.to_dict() for v in self.unit.inputs],
        }

    def save(self) -> Path:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        logger.debug("unit record written: %s", path)
        return path

    def record_verdict(self, verdict: Verdict) -> Path:
        """Persist the verdict. Called BEFORE the gate — the ordering is the requirement."""
        self.verdict = verdict
        self.verdict_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        return self.save()

    def check_against_tree(self, marked_done: Iterable[str],
                           before: Optional[Sequence[str]] = None) -> TreeDiff:
        if self.verdict is None:
            raise ValueError("no verdict to check against the tree")
        self.diff = diff_against_tree(self.verdict, marked_done, before=before)
        self.save()
        return self.diff

    def set_aside(self, condition: dict) -> Path:
        """Set this unit aside, preserving every input verdict in full."""
        self.set_aside_condition = dict(condition)
        return self.save()
