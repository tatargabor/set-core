"""The work-unit engine core: verdict, seat, lock, gate, commit, attribution.

Written with the change `work-cycle-engine-apply-first`, group 4. Every assertion here is
about a *result*, not a mechanism: "the gate ran" is compatible with the gate having been the
wrong one, so what is checked is what the engine then knows and records.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_workcycle.engine import (  # noqa: E402
    CommitOutcome,
    GateOutcome,
    GateStep,
    UnitKind,
    UnitRecord,
    WorkUnit,
    attribute_failure,
    commit_unit,
    progress_from_markers,
    run_gate,
)
from set_workcycle.lock import (  # noqa: E402
    LockHeld,
    SeatRefused,
    acquire,
    read_lock,
    release,
    validate_seat,
)
from set_workcycle.runner import build_agent_command, iter_events  # noqa: E402
from set_workcycle.verdict import (  # noqa: E402
    Outcome,
    Verdict,
    VerdictSchemaError,
    diff_against_tree,
    extract_verdict,
    parse_verdict,
)

SEAT = "session:11111111-2222-3333-4444-555555555555"


def _git_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "tree"
    tree.mkdir()
    for cmd in (["git", "init", "-q", str(tree)],
                ["git", "-C", str(tree), "config", "user.email", "t@t"],
                ["git", "-C", str(tree), "config", "user.name", "t"]):
        subprocess.run(cmd, check=True)
    (tree / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tree), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tree), "commit", "-qm", "init"], check=True)
    return tree


def _unit(tree: Path, **kw) -> WorkUnit:
    return WorkUnit(change="c", tree=tree, seat=SEAT, group_key="3", **kw)


# ── the unit is an abstraction; the kind is an attribute ──────────────────────────────────


def test_the_unit_kind_is_an_attribute_so_a_second_lane_adds_kinds_not_an_engine(tmp_path):
    """If admitting the fix lane required changing this, it would be a design error rather
    than a future task — so the enum already carries all three."""
    assert {k.value for k in UnitKind} == {"slice", "phase", "lens"}
    assert _unit(tmp_path, kind=UnitKind.LENS, lens="security").lens == "security"


# ── the verdict ───────────────────────────────────────────────────────────────────────────


def test_an_outcome_outside_the_schema_is_a_reporting_failure_not_an_inferred_outcome():
    with pytest.raises(VerdictSchemaError):
        parse_verdict({"outcome": "DONE", "summary": "x"})
    assert Outcome.FAILED_TO_REPORT.value not in Outcome.returnable(), (
        "the engine records it; a unit cannot return it"
    )


def test_a_verdict_without_a_summary_is_refused():
    with pytest.raises(VerdictSchemaError):
        parse_verdict({"outcome": "PARTIAL", "summary": "   "})


def test_a_decision_only_in_the_notes_does_not_stop_the_cycle():
    """The field is the stopper. Prose is context, and inferring a stop from prose is how a
    later section answers a human's question on their behalf."""
    v = parse_verdict({
        "outcome": "PARTIAL", "summary": "half done",
        "notes": "someone really should decide whether we support SSO",
    })
    assert v.stops is False
    assert "SSO" in v.notes, "the note still travels forward as context"


def test_a_decision_in_its_own_field_stops_the_unit():
    v = parse_verdict({
        "outcome": "NEEDS_INPUT", "summary": "blocked on a choice",
        "open_decisions": [{"task": "3.2", "question": "Which auth provider?"}],
    })
    assert v.stops is True
    assert v.open_decisions[0].task == "3.2"


def test_an_open_decision_without_a_question_is_refused():
    """A decision nobody can answer cannot be recorded as one awaiting an answer."""
    with pytest.raises(VerdictSchemaError):
        parse_verdict({"outcome": "NEEDS_INPUT", "summary": "s",
                       "open_decisions": [{"task": "3.2"}]})


def test_the_last_fenced_block_wins_so_an_example_is_not_read_as_the_answer():
    """Reading an example as an instruction is a defect class this repository names. A unit
    that shows the schema while explaining itself, then answers, must not be misread."""
    text = (
        "Here is the shape I will return:\n"
        '```json\n{"outcome": "BLOCKED", "summary": "this is only an example"}\n```\n'
        "And here is my actual verdict:\n"
        '```json\n{"outcome": "GROUP_DONE", "summary": "all four tasks done"}\n```\n'
    )
    assert extract_verdict(text).outcome is Outcome.GROUP_DONE


def test_a_unit_that_returned_nothing_is_a_reporting_failure():
    with pytest.raises(VerdictSchemaError):
        extract_verdict("")


# ── the verdict against the tree, in BOTH directions ──────────────────────────────────────


def test_claimed_more_than_the_file_marks_is_reported():
    v = parse_verdict({"outcome": "GROUP_DONE", "summary": "s", "completed": ["3.1", "3.2"]})
    d = diff_against_tree(v, marked_done=["3.1"])
    assert d.claimed_but_unmarked == ("3.2",)
    assert d.agrees is False


def test_marked_more_than_was_claimed_is_reported_too():
    """The direction that gets dropped. Work that happened and went unreported makes the next
    run's carry-over wrong, and nobody knows why."""
    v = parse_verdict({"outcome": "PARTIAL", "summary": "s", "completed": ["3.1"]})
    d = diff_against_tree(v, marked_done=["3.1", "3.2"])
    assert d.marked_but_unclaimed == ("3.2",)


def test_work_completed_by_an_earlier_run_is_not_this_unit_s_divergence():
    v = parse_verdict({"outcome": "PARTIAL", "summary": "s", "completed": ["3.2"]})
    d = diff_against_tree(v, marked_done=["3.1", "3.2"], before=["3.1"])
    assert d.agrees is True


# ── the seat and the lock ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["my-project", "wpc", "  ", "project/web"])
def test_a_seat_that_names_only_a_project_is_refused_when_it_is_recorded(bad):
    """Refused at the point of recording, not interpreted later: a value that cannot mean one
    session must never be stored as if it could. Inherited from a measured defect where a
    project-scoped seat matched seven live sessions."""
    with pytest.raises(SeatRefused):
        validate_seat(bad)


@pytest.mark.parametrize("good", ["session:abc123", "session-11111111-2222-3333-4444-555555555555"])
def test_a_session_scoped_seat_is_accepted(good):
    assert validate_seat(good).value == good


def test_a_second_unit_is_refused_while_one_holds_the_lock_and_the_holder_is_named(tmp_path):
    acquire(tmp_path, SEAT, change="c", group="3")
    with pytest.raises(LockHeld) as exc:
        acquire(tmp_path, "session:other-9999")
    assert SEAT in str(exc.value)


def test_a_lock_whose_holder_is_gone_reads_as_stale_not_as_running(tmp_path):
    acquire(tmp_path, SEAT)
    lock = tmp_path / "set/runtime/work-cycle.lock"
    data = json.loads(lock.read_text(encoding="utf-8"))
    data["pid"] = 2 ** 22  # a pid that cannot be running
    lock.write_text(json.dumps(data), encoding="utf-8")

    state = read_lock(tmp_path)
    assert state.status == "stale"
    assert state.alive is False
    acquire(tmp_path, "session:takeover-1234")  # a stale lock does not block forever


def test_releasing_someone_else_s_lock_is_refused(tmp_path):
    acquire(tmp_path, SEAT)
    assert release(tmp_path, "session:not-the-holder") is False
    assert read_lock(tmp_path).seat == SEAT


# ── the gate ──────────────────────────────────────────────────────────────────────────────


def test_no_declared_gate_means_no_gate_and_that_is_not_a_pass(tmp_path):
    """Three states, never two. 'Passed' for a project that declares no gate would claim an
    assurance nobody produced — and a section gate is already weaker than a merge gate."""
    outcome = run_gate([], tmp_path)
    assert outcome.state == "no-gate"
    assert outcome.ran is False and outcome.passed is False
    assert outcome.blocks_commit is False


def test_a_passing_gate_is_recorded_as_passed(tmp_path):
    steps = [GateStep("test", "true")]
    outcome = run_gate(steps, tmp_path, runner=lambda s, t, to: (0, ""))
    assert outcome.state == "passed" and outcome.passed is True


def test_a_failing_gate_stops_before_the_remaining_steps(tmp_path):
    calls: list[str] = []

    def runner(step, tree, timeout):
        calls.append(step.name)
        return 1, "boom"

    outcome = run_gate([GateStep("build", "x"), GateStep("test", "y")], tmp_path, runner=runner)
    assert outcome.state == "failed"
    assert outcome.failures == ("build",)
    assert calls == ["build"], "the work stays in the tree; later steps are not run"


# ── attribution ───────────────────────────────────────────────────────────────────────────


def test_a_failure_outside_this_unit_s_files_is_not_blamed_on_the_unit():
    kind, detail = attribute_failure(implicated=["other/mod.py"], unit_files=["mine/a.py"])
    assert kind == "elsewhere"
    assert "did not change" in detail


def test_a_failure_in_this_unit_s_own_files_is_attributed_to_it():
    kind, _ = attribute_failure(implicated=["mine/a.py"], unit_files=["mine/a.py", "mine/b.py"])
    assert kind == "this-unit"


def test_undeterminable_attribution_says_so_and_does_not_default_to_the_unit():
    """The cheapest wrong answer available is 'it was whoever was running'. A tree may hold
    work the engine did not do and does not control."""
    kind, detail = attribute_failure(implicated=None, unit_files=["mine/a.py"])
    assert kind == "undetermined"
    assert "NOT attributed" in detail


# ── the commit ────────────────────────────────────────────────────────────────────────────


def test_a_failed_gate_makes_no_commit_and_leaves_the_work_in_the_tree(tmp_path):
    tree = _git_tree(tmp_path)
    (tree / "new.txt").write_text("the unit's work\n", encoding="utf-8")
    unit = _unit(tree)
    gate = GateOutcome(state="failed", failures=("test",))

    result = commit_unit(unit, gate)
    assert result.committed is False and "gate failed" in result.reason
    log = subprocess.run(["git", "-C", str(tree), "log", "--oneline"],
                         capture_output=True, text=True).stdout
    assert log.count("\n") == 1, "no commit was added"
    assert (tree / "new.txt").exists(), "the work stays in the tree"


def test_a_passing_gate_commits_with_a_reference_to_the_change_and_unit(tmp_path):
    tree = _git_tree(tmp_path)
    (tree / "new.txt").write_text("the unit's work\n", encoding="utf-8")
    unit = _unit(tree)
    result = commit_unit(unit, GateOutcome(state="passed", steps=(GateStep("test", "x"),)))
    assert result.committed is True and result.sha
    message = subprocess.run(["git", "-C", str(tree), "log", "-1", "--format=%B"],
                             capture_output=True, text=True).stdout
    assert unit.change in message and unit.unit_id in message


def test_a_commit_behind_no_gate_records_that_no_gate_ran(tmp_path):
    """Allowed — a project that declares no gate steps runs with none — but the record must
    not read like a gate passed."""
    tree = _git_tree(tmp_path)
    (tree / "new.txt").write_text("x\n", encoding="utf-8")
    result = commit_unit(_unit(tree), GateOutcome(state="no-gate"))
    assert result.committed is True
    message = subprocess.run(["git", "-C", str(tree), "log", "-1", "--format=%B"],
                             capture_output=True, text=True).stdout
    assert "Gate: no-gate" in message


# ── durability and ordering ───────────────────────────────────────────────────────────────


def test_the_verdict_is_on_disk_before_the_gate_runs(tmp_path):
    """A run killed between the verdict and the commit must leave a started unit with no
    completion — not a unit that looks never attempted while its work sits in the tree."""
    tree = _git_tree(tmp_path)
    record = UnitRecord(unit=_unit(tree), started_at="2026-08-18T10:00:00+0200")
    verdict = parse_verdict({"outcome": "GROUP_DONE", "summary": "done", "completed": ["3.1"]})
    path = record.record_verdict(verdict)

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["verdict"]["outcome"] == "GROUP_DONE"
    assert on_disk["gate"] is None, "the gate had not run yet"
    assert on_disk["commit"] is None


def test_setting_a_comparing_unit_aside_preserves_every_input_verdict_in_full(tmp_path):
    """What a reader needs at that moment is WHERE the inputs diverged, which a summary has
    already thrown away."""
    inputs = tuple(
        parse_verdict({"outcome": "PARTIAL", "summary": f"lens {n} found something",
                       "notes": f"detail from {n}"})
        for n in ("security", "performance", "correctness")
    )
    unit = _unit(tmp_path, kind=UnitKind.LENS, inputs=inputs)
    record = UnitRecord(unit=unit)
    path = record.set_aside({"kind": "human-decision", "question": "which lens wins?"})

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert len(on_disk["inputs"]) == 3
    assert [i["summary"] for i in on_disk["inputs"]] == [v.summary for v in inputs]
    assert all(i["notes"] for i in on_disk["inputs"]), "no input was replaced by a summary"


# ── progress comes from the tree ──────────────────────────────────────────────────────────


def test_progress_is_derived_from_task_markers(tmp_path):
    assert progress_from_markers(3, 8) == {
        "done": 3, "total": 8, "percent": 37.5, "derived_from": "task markers"}


def test_no_engine_module_derives_progress_from_an_activity_counter():
    """The test task 4.10 names. An activity counter rises while a unit is stuck as readily
    as while it is working, so reporting one as progress reports the opposite of what the
    reader asked. This scans for a *progress* value computed from a turn/event/message count.
    """
    package = REPO / "lib" / "set_workcycle"
    counters = {"num_turns", "turns", "event_count", "events", "message_count", "n_events"}
    offenders: list[str] = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # `progress = <expr>` / `"percent": <expr>` where <expr> mentions a counter
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            if not any("progress" in t or "percent" in t for t in targets):
                continue
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
                n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            bad = names & counters
            if bad:
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: {sorted(bad)}")
    assert not offenders, "progress derived from an activity counter:\n  " + "\n  ".join(offenders)


# ── the session, and the seat it yields ───────────────────────────────────────────────────


def test_the_session_id_is_read_off_the_stream_not_invented():
    events = list(iter_events([
        '{"type":"system","subtype":"init","session_id":"sess-42"}',
        "a diagnostic line that is not JSON",
        '{"type":"result","result":"done"}',
    ]))
    assert [e.type for e in events] == ["system", "result"], "a non-JSON line is skipped"
    assert events[0].session_id == "sess-42"


def test_the_unit_is_invoked_as_a_full_session_with_the_project_s_own_rules():
    """No chat context, no resume, no permission mode chosen on the session's behalf — those
    are chat's flags, and a unit running under different rules than the project enforces is
    not exercising the project's rules."""
    cmd = build_agent_command("do the work")
    assert cmd[:2] == ["claude", "-p"]
    assert "--output-format" in cmd and "stream-json" in cmd
    for chat_flag in ("--append-system-prompt", "--resume", "--permission-mode"):
        assert chat_flag not in cmd


# ── the gate configuration comes from the existing chain, not from the engine ─────────────


def test_gate_steps_come_from_the_resolved_profile_and_the_engine_supplies_none(tmp_path):
    """The one thing the design fixed in advance: exactly one source of gate configuration.
    The engine contributes no gate names and no commands — a profile that detects nothing
    yields no steps, and no step is invented to fill the gap."""
    from set_orch.gate_profiles import resolve_gate_config
    from set_orch.state import Change
    from set_workcycle.engine import resolve_gate_steps

    class SilentProfile:
        """Detects nothing. The correct result is zero steps, not a guessed default."""

        def detect_build_command(self, p): return None
        def detect_test_command(self, p): return None
        def detect_e2e_command(self, p): return None

    class TellingProfile(SilentProfile):
        def detect_test_command(self, p): return "pytest -q"

    change = Change(name="c")
    assert resolve_gate_config(change, SilentProfile(), None, tmp_path).gate_names()
    assert resolve_gate_steps(change, SilentProfile(), tmp_path) == []

    steps = resolve_gate_steps(change, TellingProfile(), tmp_path)
    assert [(s.name, s.command) for s in steps] == [("test", "pytest -q")]


def test_the_engine_package_names_no_gate_command_of_its_own():
    """A grep would be a substring test; this reads the source. The engine may name a *gate*
    (`test`, `build`) because those come from the resolution chain — what it must not carry
    is a command, which is where a project's tooling would leak into Layer 1."""
    import re

    package = REPO / "lib" / "set_workcycle"
    tooling = ("pytest", "npm", "pnpm", "yarn", "playwright", "prisma", "vitest", "tsc",
               "eslint", "cargo", "gradle")
    # WORD boundaries, not substrings. The first draft of this test used `t in low` and
    # reported `tsc` twice — from `VerdictSchemaError`, i.e. verdic-tSc-hemaError. The
    # assertion below keeps that refuted pattern in the file so a later "simplification"
    # back to a substring check fails instead of looking identical and checking nothing.
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, tooling)) + r")\b")
    offenders = []
    naive_only = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                low = node.value.lower()
                if pattern.search(low):
                    offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: {node.value[:60]!r}")
                elif any(t in low for t in tooling):
                    naive_only.append(f"{path.relative_to(REPO)}:{node.lineno}")
    assert not offenders, "project tooling named inside the engine:\n  " + "\n  ".join(offenders)
    assert naive_only, (
        "a bare substring check would no longer produce a false positive here, so this test "
        "no longer demonstrates why the word boundary is needed — check before relaxing it"
    )


# ── the project's DECLARED gate is the one that runs ──────────────────────────────────────


def _adoption(gates, *, declared=True):
    from set_workcycle.adoption import Adoption

    return Adoption(adopted=True, changes_dir="changes", gates=tuple(gates),
                    gates_declared=declared)


class _LoudProfile:
    """Detects a command that is NOT the declared one, so a fallback is visible in the result
    rather than merely suspected. A profile that detected nothing would let the weaker
    assertion pass on the broken code too."""

    def detect_build_command(self, p): return None
    def detect_test_command(self, p): return "profile-detected-check"
    def detect_e2e_command(self, p): return None


def test_the_declared_commands_are_the_ones_that_actually_run(tmp_path):
    """The strong form, asked for by the consumer: assert the declared COMMAND executed, not
    that *a* gate ran. A profile-detected gate goes green exactly like a declared one, so
    "the gate passed" is compatible with the declaration having been ignored — which is the
    state this repo shipped in until it was measured.

    Fail direction: the weaker assertion leaves the bug in place and paints it green.
    """
    from set_orch.state import Change
    from set_workcycle.engine import resolve_gate_steps, run_gate

    declared = ["a-declared-check --one", "a-declared-check --two"]
    steps = resolve_gate_steps(Change(name="c"), _LoudProfile(), tmp_path,
                               adoption=_adoption(declared))

    executed: list[str] = []
    outcome = run_gate(steps, tmp_path, runner=lambda s, t, to: (executed.append(s.command), (0, ""))[1])

    assert executed == declared, f"the declared commands did not run; ran: {executed}"
    assert "profile-detected-check" not in executed
    assert outcome.state == "passed"
    assert set(outcome.outputs) == set(s.name for s in steps)


def test_declaring_the_gate_key_empty_means_no_gate_and_never_a_detected_one(tmp_path):
    """`gates: []` is an answer, not a gap. Falling back to detection here would hand a
    project that deliberately narrowed its gate a wider one it never asked for — and the
    green would be indistinguishable from its own gate having run.

    ⚠ The first version of this test used a profile that RAISED if consulted, and the
    mutant that falls back to detection passed it — `resolve_gate_steps` wraps the detector
    in `except Exception`, so the explosion became a logged warning and an empty command,
    and "no steps" arrived for the wrong reason. The raise measured the CALL; what decides
    is the RESULT. The profile below therefore detects a real command, so a fallback
    produces a step and the assertion has something to fail on.
    """
    from set_orch.state import Change
    from set_workcycle.engine import resolve_gate_steps, run_gate

    consulted: list[str] = []

    class _RecordingProfile(_LoudProfile):
        def detect_test_command(self, p):
            consulted.append("test")
            return "profile-detected-check"

    steps = resolve_gate_steps(Change(name="c"), _RecordingProfile(), tmp_path,
                               adoption=_adoption([]))
    assert steps == [], f"an empty declaration was answered a second time: {steps}"
    assert consulted == [], "the profile was consulted despite an explicit empty declaration"
    assert run_gate(steps, tmp_path).state == "no-gate"


def test_a_project_that_declared_no_gate_key_still_gets_the_profile_chain(tmp_path):
    """The other half of the distinction the `Adoption` dataclass already carried: *not
    declared* is not *declared empty*, and only the second one silences the profile."""
    from set_orch.state import Change
    from set_workcycle.engine import resolve_gate_steps

    steps = resolve_gate_steps(Change(name="c"), _LoudProfile(), tmp_path,
                               adoption=_adoption([], declared=False))
    assert [(s.name, s.command) for s in steps] == [("test", "profile-detected-check")]


def test_two_identical_declared_commands_are_both_recorded(tmp_path):
    """`GateOutcome.outputs` is keyed on the step name. Collapsing duplicates would drop one
    run's output while the count still read as two — a gap that looks like data."""
    from set_orch.state import Change
    from set_workcycle.engine import resolve_gate_steps, run_gate

    steps = resolve_gate_steps(Change(name="c"), _LoudProfile(), tmp_path,
                               adoption=_adoption(["same-check", "same-check"]))
    assert len(steps) == 2
    outcome = run_gate(steps, tmp_path, runner=lambda s, t, to: (0, f"out:{s.name}"))
    assert len(outcome.outputs) == 2


def test_the_cli_passes_the_adoption_into_gate_resolution(tmp_path):
    """The bug was not in the resolver, it was that nobody handed it the declaration. This
    reads the call site: a resolver that can honour the declaration and a caller that never
    passes it look identical from inside `engine.py`.
    """
    import ast

    src = (REPO / "lib" / "set_workcycle" / "cli.py").read_text(encoding="utf-8")
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "resolve_gate_steps"]
    assert calls, "resolve_gate_steps is not called from the CLI at all"
    for call in calls:
        assert any(kw.arg == "adoption" for kw in call.keywords), (
            f"cli.py:{call.lineno} resolves gate steps without the project's declaration")
