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


def test_a_failure_naming_only_other_files_is_UNDETERMINED_not_exonerating():
    """⚠ This asserted `elsewhere` until a live cross-run showed what that word licenses.

    A file set scraped from gate output is not a list of causes: it picks names out of PROSE
    (a remediation hint naming the file to EDIT), out of PASSING lines, and it can never
    reach an INDIRECT cause — the measured case was a task file this unit did change, feeding
    a generated artefact whose name was the only thing the failure mentioned. So "none of my
    files are named" is not evidence of innocence, and `elsewhere` reads as exactly that.
    """
    kind, detail = attribute_failure(implicated=["other/mod.py"], unit_files=["mine/a.py"])
    assert kind == "undetermined"
    assert "not evidence of innocence" in detail
    assert "NOT attributed to this unit" in detail


def test_elsewhere_survives_only_where_there_IS_positive_evidence():
    """A unit that changed nothing cannot have broken anything — that one is provable, so it
    keeps the exonerating verdict. The distinction is the point: `elsewhere` is now a claim
    that has to be earned, not the default for 'no intersection'."""
    kind, detail = attribute_failure(implicated=["other/mod.py"], unit_files=[])
    assert kind == "elsewhere"
    assert "changed no file" in detail


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


# ── the three gates the first live cross-run found ────────────────────────────────────────


def test_the_empty_path_is_not_a_named_file(tmp_path):
    """`(root / "").exists()` is True, so a bare `.` or `./` anywhere in the output used to
    enter the implicated set as a file. Measured live: the list began with `''`. A phantom
    entry inflates the set, which pushes the intersection toward empty — i.e. toward the
    exonerating answer."""
    from set_workcycle.engine import _implicated_files

    (tmp_path / "real.py").write_text("x", encoding="utf-8")
    found = _implicated_files("failed at . and ./ and real.py", tmp_path)
    assert found == {"real.py"}, f"a phantom path entered the set: {found}"


def test_a_failed_gate_reports_that_the_agent_ALREADY_COMMITTED(tmp_path):
    """The engine used to state "the work stays in the tree" without looking at the tree.
    Measured live: the agent had committed before the gate ran, so the record said
    `committed: false` and "stays in the tree" while the commit sat in the history.

    The engine cannot stop this — the agent holds git — but it must not report a tree state
    it never measured.
    """
    from set_workcycle.engine import GateOutcome, WorkUnit, commit_unit

    unit = WorkUnit(change="c", tree=tmp_path, seat="session:t", group_key="0")
    gate = GateOutcome(state="failed", failures=("check",))

    def fake_git(argv):
        return (0, "cafebabe0000\n") if "rev-parse" in argv else (0, "")

    out = commit_unit(unit, gate, runner=fake_git, baseline="deadbeef0000")
    assert out.committed is False
    assert out.committed_by_agent == "cafebabe0000", "the moved tree was not detected"
    assert "ALREADY" in out.reason and "NOT holding it" in out.reason

    same = commit_unit(unit, gate, runner=fake_git, baseline="cafebabe0000")
    assert same.committed_by_agent == "", "an unmoved tree must not be reported as committed"
    assert "stays in the tree" not in same.reason or same.committed_by_agent == ""


def test_the_agent_commit_reaches_the_RECORD_not_only_the_return_value(tmp_path):
    """A field the record does not serialise is a field nobody downstream can act on — the
    same defect this change shipped once already with the project's declared gates."""
    from set_workcycle.engine import CommitOutcome, UnitRecord, WorkUnit

    rec = UnitRecord(unit=WorkUnit(change="c", tree=tmp_path, seat="session:t", group_key="0"))
    rec.commit = CommitOutcome(False, reason="gate failed", committed_by_agent="abc123")
    assert rec.to_dict()["commit"]["committed_by_agent"] == "abc123"


def test_the_commit_never_stages_the_engines_own_run_records(tmp_path):
    """Measured live in a consumer tree: `git add -A` staged the engine's run record. The
    commit failed on an unrelated lock, so nothing landed — but the next green gate would
    have written this engine's bookkeeping into the project's history as project work.

    Asserted on the argv rather than on a real repository, because what went wrong is the
    command that was issued.
    """
    from set_workcycle.engine import RUN_STATE_DIR, GateOutcome, WorkUnit, commit_unit

    calls: list[list[str]] = []

    def fake_git(argv):
        calls.append(list(argv))
        if "check-ignore" in argv:
            return (1, "")  # this project does NOT already ignore the run state
        if "commit" in argv:
            return (1, "nothing to commit, working tree clean")
        return (0, "")

    commit_unit(WorkUnit(change="c", tree=tmp_path, seat="s", group_key="0"),
                GateOutcome(state="passed"), runner=fake_git)

    add = next(c for c in calls if "add" in c)
    assert f":(exclude){RUN_STATE_DIR}" in add, f"run records are not excluded: {add}"


# --------------------------------------------------------------------------- #
# What a run records about its origin — work-cycle-run-visibility §2
# --------------------------------------------------------------------------- #

def test_an_undeclared_origin_is_absent_rather_than_a_plausible_word(tmp_path):
    """The defect this task fixes was a DEFAULT, not a missing field.

    `--started-by` defaulted to the word `agent`, so every run carried a
    plausible-looking origin and a reader could not tell a stated one from an
    unstated one. A default that reads like a declaration is worse than no field
    at all: it is a false value, and it is the shape somebody builds on.
    """
    from set_workcycle.engine import UnitKind, UnitRecord, WorkUnit

    unit = WorkUnit(change="c", tree=tmp_path, seat="s", kind=UnitKind.SLICE, group_key="1")
    assert UnitRecord(unit=unit).to_dict()["started_by"] is None
    assert UnitRecord(unit=unit, started_by="set-core#abc").to_dict()["started_by"] == "set-core#abc"


def test_the_origin_travels_marked_as_a_claim(tmp_path):
    """Nothing verified it, so nothing may render it as verified.

    The marker travels IN the record rather than being applied by whichever
    surface happens to read it — a rule that lives only in a renderer is a rule
    the next renderer does not have.
    """
    from set_workcycle.engine import UnitKind, UnitRecord, WorkUnit

    d = UnitRecord(unit=WorkUnit(change="c", tree=tmp_path, seat="s",
                                 kind=UnitKind.SLICE, group_key="1"),
                   started_by="set-core#abc").to_dict()
    assert d["started_by_is_claim"] is True


def test_a_session_that_never_announced_an_id_is_unknown_not_absent(tmp_path):
    """`None` here means *never announced*, and must not read as *had no session*."""
    from set_workcycle.engine import UnitKind, UnitRecord, WorkUnit

    unit = WorkUnit(change="c", tree=tmp_path, seat="s", kind=UnitKind.SLICE, group_key="1")
    assert UnitRecord(unit=unit).to_dict()["session_id"] is None
    assert UnitRecord(unit=unit, session_id="sess-1").to_dict()["session_id"] == "sess-1"


def test_the_origin_is_on_the_record_before_the_session_starts(tmp_path, monkeypatch):
    """A run killed in its first second still says who asked for it.

    Asserted at the moment the engine writes, not after the run — the harness's
    own teardown must not be what answers.
    """
    import json
    from set_workcycle import cli as wc_cli

    seen = {}

    def _fake_agent(prompt, tree, model=None):
        # Read the record from DISK at the moment the session would start.
        root = tmp_path / "set/runtime/work-cycle/demo"
        seen["on_disk"] = [json.loads(p.read_text()) for p in root.glob("*.json")]
        raise RuntimeError("stop here — the origin has already been asserted")

    monkeypatch.setattr(wc_cli, "_AGENT_RUNNER", _fake_agent)
    monkeypatch.setattr(wc_cli, "run_agent_session", _fake_agent)
    # Drive `_drive` directly with the smallest real objects it needs.
    from set_workcycle.engine import UnitKind, WorkUnit

    class _Args:
        change = "demo"; limit = None; model = ""; dry_run = False
        started_by = "set-core#whoasked"

    class _View:
        tree = tmp_path
        tasks_path = None
        plan = None
        adoption = None

    (tmp_path / "openspec/changes/demo").mkdir(parents=True)
    (tmp_path / "openspec/changes/demo/tasks.md").write_text("## 1. g\n\n- [ ] 1.1 do it\n")
    _View.tasks_path = tmp_path / "openspec/changes/demo/tasks.md"
    from set_workcycle.groups import parse_task_groups
    _View.plan = parse_task_groups(_View.tasks_path)
    group = _View.plan.groups[0]
    unit = WorkUnit(change="demo", tree=tmp_path, seat="s", kind=UnitKind.SLICE,
                    group_key=group.key)

    with pytest.raises(RuntimeError):
        wc_cli._drive(unit, _View(), group, _Args(), [])

    assert seen["on_disk"], "no record on disk when the session was about to start"
    assert seen["on_disk"][0]["started_by"] == "set-core#whoasked"


# --------------------------------------------------------------------------- #
# The run's stream — work-cycle-run-visibility §3
# --------------------------------------------------------------------------- #

def test_the_stream_is_written_under_the_tree_the_engine_was_given(tmp_path):
    """Confidentiality by construction, asserted for a tree that is NOT this repo.

    The stream carries the project's own domain. It lands in the project's runtime
    area or the framework has persisted a consumer's data — which is a defect, not
    a storage preference.
    """
    from set_workcycle.engine import UnitKind, UnitRecord, WorkUnit

    elsewhere = tmp_path / "some-other-project"
    rec = UnitRecord(unit=WorkUnit(change="c", tree=elsewhere, seat="s",
                                   kind=UnitKind.SLICE, group_key="1"))
    assert rec.stream_path().is_relative_to(elsewhere)
    assert rec.stream_path().parent == rec.path().parent
    # And it is not derived from anything ambient.
    assert "set-core" not in str(rec.stream_path())


def test_a_killed_run_keeps_every_event_it_had_produced(tmp_path):
    """Incremental, not buffered — and asserted by never closing the sink.

    A run killed mid-way is exactly the run somebody wants to read, so a final
    write would lose it at the moment it matters most.
    """
    from set_workcycle.runner import AgentEvent, StreamSink

    sink = StreamSink(tmp_path / "u.stream.jsonl").open()
    sink.write(AgentEvent(type="a", payload={"type": "a"}))
    sink.write(AgentEvent(type="b", payload={"type": "b"}))
    # No close(): the process died here.
    lines = (tmp_path / "u.stream.jsonl").read_text().splitlines()
    assert [json.loads(l)["type"] for l in lines] == ["a", "b"]
    assert StreamSink.TERMINATOR not in (tmp_path / "u.stream.jsonl").read_text()


def test_a_finished_stream_is_distinguishable_from_a_truncated_one(tmp_path):
    from set_workcycle.runner import AgentEvent, StreamSink

    with StreamSink(tmp_path / "u.stream.jsonl") as sink:
        sink.write(AgentEvent(type="a", payload={"type": "a"}))
    last = json.loads((tmp_path / "u.stream.jsonl").read_text().splitlines()[-1])
    assert last["type"] == StreamSink.TERMINATOR
    assert last["events"] == 1


def test_a_session_that_said_nothing_is_not_the_same_as_no_session(tmp_path):
    """Three states, not two — and the middle one is the one that gets flattened."""
    from set_workcycle.runner import StreamSink

    # No session started: no file at all.
    assert not (tmp_path / "never.stream.jsonl").exists()

    # A session ran and produced nothing: the file exists and says so.
    with StreamSink(tmp_path / "silent.stream.jsonl"):
        pass
    lines = (tmp_path / "silent.stream.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["events"] == 0


def test_a_sink_that_cannot_write_does_not_end_a_working_run(tmp_path, caplog):
    """Named, never swallowed — and never fatal to the unit.

    The count on the record still says how many events reached it, so the loss is
    visible rather than silent.
    """
    from set_workcycle.runner import AgentEvent, StreamSink

    sink = StreamSink(tmp_path / "u.stream.jsonl").open()
    sink._fh.close()                      # the file handle dies under it
    with caplog.at_level("WARNING"):
        sink.write(AgentEvent(type="a", payload={"type": "a"}))
    assert sink.events == 0
    assert any("run stream" in r.message for r in caplog.records)


def test_the_runner_is_asked_for_its_signature_not_tried_and_retried(tmp_path):
    """The hazard this replaced: a `TypeError` from INSIDE a runner would have
    been read as "this runner takes no on_event" and started a SECOND session for
    one unit. A signature is a question with an answer; a failed call is not.
    """
    import inspect
    from set_workcycle import cli as wc_cli

    src = inspect.getsource(wc_cli._drive)
    assert "inspect.signature(agent)" in src
    assert "except TypeError:\n        # A runner that does not take" not in src


def test_no_framework_log_about_a_run_carries_text_from_its_stream(tmp_path, caplog):
    """Asserted on the OUTPUT, not on the intent.

    Found by writing this test: `iter_events` logged up to 200 characters of any
    non-JSON line, so a DEBUG log became a place the framework persisted a
    consumer's domain data. Counts and identifiers are what a log needs.
    """
    from set_workcycle.runner import iter_events

    secret = "PARTNER-NAME-AND-ORDER-12345 quoted from the session"
    with caplog.at_level("DEBUG"):
        events = list(iter_events([secret, '{"type":"system","session_id":"s1"}']))

    assert len(events) == 1                      # the junk line was skipped, not fatal
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert secret not in joined
    assert "PARTNER" not in joined
    assert str(len(secret)) in joined            # the shape IS reported


# --------------------------------------------------------------------------- #
# B-108 — the exclusion that broke the commit it was protecting
# --------------------------------------------------------------------------- #


def _real_repo(tmp_path):
    """A real repository with the run-state area gitignored — the shape this engine's own
    adoption note recommends, and the shape in which B-108 appeared."""
    import subprocess

    def git(*argv):
        proc = subprocess.run(["git", "-C", str(tmp_path), *argv],
                              capture_output=True, text=True)
        assert proc.returncode == 0, f"{argv}: {proc.stderr}"
        return proc.stdout

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "T")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", str(tmp_path / ".no-hooks"))
    (tmp_path / ".gitignore").write_text("/set/*\n!/set/work-cycle.yaml\n")
    git("add", "--", ".gitignore")
    git("commit", "-q", "-m", "base")
    return git


def test_a_unit_commits_in_a_project_whose_run_state_directory_is_gitignored(tmp_path):
    """B-108, measured on the first real work unit ever driven from the fleet screen: the
    verdict was green, the gate was green, the product was on disk — and the record said
    `commit: false, reason: "git add failed"`.

    Driven with the REAL git runner, in a real repository, because that is precisely what
    the previous test of this behaviour did not do. Its argv was correct; git's answer to
    that argv was not, and a fake runner cannot disagree with the command it is given.
    """
    from set_workcycle.engine import RUN_STATE_DIR, GateOutcome, WorkUnit, commit_unit

    git = _real_repo(tmp_path)
    record = tmp_path / RUN_STATE_DIR / "c"
    record.mkdir(parents=True)
    (record / "c--1.json").write_text("{}")          # the engine's own bookkeeping
    (tmp_path / "product.txt").write_text("the unit's work\n")

    outcome = commit_unit(WorkUnit(change="c", tree=tmp_path, seat="s", group_key="1"),
                          GateOutcome(state="passed"))

    assert outcome.committed, f"the unit did not commit: {outcome.reason}"
    committed = git("show", "--name-only", "--format=", "HEAD").split()
    assert "product.txt" in committed, committed
    assert not [f for f in committed if f.startswith("set/runtime")], (
        f"the engine's run state reached the project's history: {committed}")


def test_the_exclusion_is_kept_where_git_does_not_already_ignore_the_run_state(tmp_path):
    """The other half, and it is the half that must not be lost: where the project does NOT
    ignore the run state, dropping the exclusion would commit this engine's bookkeeping into
    someone else's repository as if it were their work."""
    from set_workcycle.engine import RUN_STATE_DIR, GateOutcome, WorkUnit, commit_unit

    git = _real_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("")          # nothing is ignored any more
    git("add", "--", ".gitignore")
    git("commit", "-q", "-m", "stop ignoring set/")
    record = tmp_path / RUN_STATE_DIR / "c"
    record.mkdir(parents=True)
    (record / "c--1.json").write_text("{}")
    (tmp_path / "product.txt").write_text("the unit's work\n")

    outcome = commit_unit(WorkUnit(change="c", tree=tmp_path, seat="s", group_key="1"),
                          GateOutcome(state="passed"))

    assert outcome.committed, f"the unit did not commit: {outcome.reason}"
    committed = git("show", "--name-only", "--format=", "HEAD").split()
    assert "product.txt" in committed, committed
    assert not [f for f in committed if f.startswith("set/runtime")], (
        f"the engine's run state reached the project's history: {committed}")


def test_a_failed_add_reports_gits_own_sentence_not_the_name_of_the_command(tmp_path):
    """The second, smaller defect in the same line: the reason named the command and threw
    away the message that said what was wrong. A caller cannot act on `git add failed`."""
    from set_workcycle.engine import GateOutcome, WorkUnit, commit_unit

    def fake_git(argv):
        if "check-ignore" in argv:
            return (1, "")
        if "add" in argv:
            return (1, "fatal: Unable to create '.git/index.lock': File exists.")
        return (0, "")

    outcome = commit_unit(WorkUnit(change="c", tree=tmp_path, seat="s", group_key="1"),
                          GateOutcome(state="passed"), runner=fake_git)

    assert not outcome.committed
    assert "index.lock" in outcome.reason, outcome.reason
