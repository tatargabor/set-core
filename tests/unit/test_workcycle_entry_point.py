"""One entry point, and everything that follows from there being exactly one.

Written with the change `work-cycle-engine-apply-first`, group 6 (and the two tasks of group
5 that could only be finished once an entry point existed).

The property under test is unusual in that it is about *absence*: no second way to start a
unit, and no path that skips answer intake. Both are checked structurally rather than by
exercising the paths one at a time — an enumeration is only ever as complete as the list
somebody remembered to update.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_workcycle.cli import (  # noqa: E402
    build_parser,
    cmd_answer,
    cmd_run,
    cmd_status,
    main,
    open_engine,
    read_run_state,
)
from set_workcycle.connector import mark_awaiting, write_answer  # noqa: E402
from set_workcycle.engine import RUN_STATE_DIR, UnitRecord, WorkUnit  # noqa: E402
from set_workcycle.lock import acquire  # noqa: E402

SEAT = "session:11111111-2222-3333-4444-555555555555"
VERDICT = '```json\n{"outcome": "GROUP_DONE", "summary": "the slice is done", "completed": ["1.1"]}\n```'
CLI = REPO / "lib" / "set_workcycle" / "cli.py"


def _project(tmp_path: Path, tasks: str = None, *, declare: bool = True) -> Path:
    """A project that has declared itself. `declare=False` yields an un-adopted tree — the
    engine refuses to guess where changes live, so the declaration is what makes it a
    project at all."""
    d = tmp_path / "openspec" / "changes" / "c"
    d.mkdir(parents=True)
    if declare:
        (tmp_path / "set").mkdir(exist_ok=True)
        (tmp_path / "set" / "work-cycle.yaml").write_text(
            "changes_dir: openspec/changes\n", encoding="utf-8")
    (d / "tasks.md").write_text(tasks or (
        "## 1. First\n- [ ] 1.1 alpha\n\n## 2. Second\n<!-- depends: none -->\n- [ ] 2.1 bravo\n"
    ), encoding="utf-8")
    return tmp_path


def _run(tmp_path: Path, *argv: str) -> tuple[int, dict]:
    """Run the command in-process and return (exit code, parsed JSON payload)."""
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["--tree", str(tmp_path), "--json", *argv])
    return code, json.loads(buf.getvalue())


# ── 6.1 / 6.2 the command ─────────────────────────────────────────────────────────────────


def test_the_command_runs_from_the_project_s_tree_with_no_service_and_no_network(tmp_path):
    """Run as a real subprocess with the network stripped from its environment, so the claim
    is about the program rather than about this test's imports."""
    _project(tmp_path)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(REPO / "lib"),
        "HOME": str(tmp_path),
        # Any outbound call would have to go through these; pointing them at a closed port
        # means a network attempt fails rather than silently succeeding.
        "http_proxy": "http://127.0.0.1:1", "https_proxy": "http://127.0.0.1:1",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "set_workcycle.cli", "--tree", str(tmp_path),
         "--change", "c", "--json", "status"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["selected"] == "1"


def test_nothing_runnable_reports_a_reason_per_group(tmp_path):
    _project(tmp_path, "## 1. First\n- [?] 1.1 needs a person\n\n## 2. Second\n- [ ] 2.1 b\n")
    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert code == 1 and payload["started"] is False
    assert set(payload["reasons"]) == {"1", "2"}
    assert "awaiting" in payload["reasons"]["1"]


def test_a_unit_already_holding_the_lock_refuses_the_second_and_names_the_holder(tmp_path):
    _project(tmp_path)
    acquire(tmp_path, SEAT, change="c", group="1")
    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", "session:other-2222")
    assert code == 5 and payload["holder"] == SEAT


def test_a_project_scoped_seat_is_refused_at_the_command(tmp_path):
    _project(tmp_path)
    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", "my-project")
    assert code == 4 and payload["started"] is False


# ── 6.3 there is exactly one way in ───────────────────────────────────────────────────────


def test_only_one_interface_starts_a_work_unit():
    """The test task 6.3 asks for. It fails when a second subcommand declares that it starts
    a unit — which is the shape a second start path would actually take here."""
    parser = build_parser()
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert len(subparsers) == 1
    starters = [
        name for name, sub in subparsers[0].choices.items()
        if sub.get_default("starts_a_unit")
    ]
    assert starters == ["run"], f"exactly one interface may start a unit; found {starters}"


def test_no_module_in_the_engine_package_spawns_a_unit_outside_the_command():
    """A second start path would not have to be a subcommand — it could be a function that
    acquires the lock and builds a unit. Only the command module may do both."""
    package = REPO / "lib" / "set_workcycle"
    offenders = []
    for path in sorted(package.rglob("*.py")):
        if path.name in {"cli.py", "engine.py", "lock.py"}:
            continue
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        calls = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        if "acquire" in calls and "WorkUnit" in calls:
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, f"a second start path: {offenders}"


def test_an_agent_started_run_and_a_surface_started_run_produce_the_same_state_shape(
        tmp_path, agent_runner):
    """The surface invokes the same command an agent would. What differs is a recorded field
    saying who started it — never the shape of what gets written."""
    agent_runner(VERDICT)
    _project(tmp_path)
    _, agent = _run(tmp_path, "--change", "c", "run", "--seat", SEAT, "--started-by", "agent")
    _, surface = _run(tmp_path, "--change", "c", "run", "--seat", "session:surface-3333",
                      "--started-by", "surface")

    assert agent.keys() == surface.keys()
    assert agent["unit_id"] == surface["unit_id"] and agent["group"] == surface["group"]
    assert (agent["started_by"], surface["started_by"]) == ("agent", "surface")


# ── 6.4 run state is readable without running anything ────────────────────────────────────


def test_run_state_is_read_off_disk_without_starting_a_process(tmp_path):
    tree = tmp_path
    record = UnitRecord(unit=WorkUnit(change="c", tree=tree, seat=SEAT, group_key="1"),
                        started_at="2026-08-18T10:00:00+0200", pid=os.getpid())
    record.save()
    states = read_run_state(tree, "c")
    assert [s["unit_id"] for s in states] == ["c--1"]
    assert states[0]["_status"] == "running"


def test_a_finished_run_still_reports_its_outcome_after_its_process_is_gone(tmp_path):
    record = UnitRecord(unit=WorkUnit(change="c", tree=tmp_path, seat=SEAT, group_key="1"),
                        pid=2 ** 22)
    record.set_aside({"kind": "human-decision", "detail": "which provider?"})
    states = read_run_state(tmp_path, "c")
    assert states[0]["_status"] == "finished"
    assert states[0]["set_aside"]["detail"] == "which provider?"


def test_a_stale_claim_is_distinguishable_from_a_live_run(tmp_path):
    """A record that merely exists proves nothing about a run — which is exactly what a
    reader would otherwise conclude from finding one."""
    record = UnitRecord(unit=WorkUnit(change="c", tree=tmp_path, seat=SEAT, group_key="1"),
                        pid=2 ** 22)
    record.save()
    assert read_run_state(tmp_path, "c")[0]["_status"] == "stale"


# ── 5.6 / 6.5 intake on EVERY path, checked structurally ──────────────────────────────────


def test_every_command_takes_in_answers_because_none_can_get_state_without_it():
    """Task 5.8's named case: a test that fails if intake is reachable from only some entry
    points.

    Checked structurally rather than by calling each command, because an enumeration is only
    as complete as the list somebody remembered to update. `intake()` is called from exactly
    one place — `open_engine` — and every command either calls `open_engine` or does not read
    state at all.
    """
    tree = ast.parse(CLI.read_text(encoding="utf-8"), filename=str(CLI))
    functions = {n.name: n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    callers_of_intake = {
        name for name, node in functions.items()
        if any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "intake"
               for c in ast.walk(node))
    }
    assert callers_of_intake == {"open_engine"}, (
        f"intake must have exactly one call site so no path can skip it; found "
        f"{sorted(callers_of_intake)}"
    )

    commands = {name for name in functions if name.startswith("cmd_")}
    assert commands, "no commands found — the scan itself is broken"
    for name in sorted(commands):
        node = functions[name]
        calls = {getattr(c.func, "id", "") for c in ast.walk(node) if isinstance(c, ast.Call)}
        reads_state = bool(calls & {"open_engine", "read_run_state", "select_next_group"})
        if reads_state:
            assert "open_engine" in calls, f"{name} reads state without taking in answers"


def test_a_reporting_only_invocation_still_takes_in_answers(tmp_path):
    """The measured failure: correct intake existed but lived in the rarely-called variant,
    so questions went unanswered while the code that answered them was right there."""
    _project(tmp_path)
    tasks = tmp_path / "openspec/changes/c/tasks.md"
    mark_awaiting(tasks, "1.1", "Which provider?")
    write_answer(tmp_path, "c", "1.1", "OIDC", source="dashboard")

    code, payload = _run(tmp_path, "--change", "c", "status")
    assert code == 0
    assert any("applied c#1.1" in line for line in payload["lines"]), payload["lines"]


def test_an_answer_placed_before_a_run_is_taken_in_before_the_group_is_selected(
        tmp_path, agent_runner):
    agent_runner('```json\n{"outcome": "PARTIAL", "summary": "started"}\n```')
    _project(tmp_path, "## 1. First\n- [ ] 1.1 alpha\n- [ ] 1.2 bravo\n")
    tasks = tmp_path / "openspec/changes/c/tasks.md"
    mark_awaiting(tasks, "1.1", "Which provider?")

    code, blocked = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert code == 1 and "awaiting" in blocked["reasons"]["1"]

    write_answer(tmp_path, "c", "1.1", "OIDC", source="dashboard")
    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert any("applied c#1.1" in line for line in payload["lines"]), payload["lines"]


def test_an_un_adopted_project_is_never_reported_as_having_nothing_to_do(tmp_path):
    code, payload = _run(tmp_path, "status")
    assert code == 2
    assert payload["adopted"] is False
    assert payload["missing"]
    assert "selected" not in payload, "no runnable-group answer is offered for a non-project"


# ── the lifecycle the command actually drives ─────────────────────────────────────────────
#
# Added after a self-caught defect: the command existed, acquired the lock and reported
# "started", and drove nothing. Every test above passed. The name claimed more than the code
# delivered, which is the marker-true-of-a-narrower-subject failure — and the tests below are
# what makes "starts a unit" mean the whole cycle.


def _lifecycle_project(tmp_path: Path) -> Path:
    _project(tmp_path, "## 1. First\n- [ ] 1.1 alpha\n- [ ] 1.2 bravo\n")
    (tmp_path / "openspec" / "changes" / "c" / "proposal.md").write_text("why\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


def test_a_run_goes_all_the_way_through_verdict_gate_and_commit(tmp_path, agent_runner):
    def did_the_work(tree: Path) -> None:
        """What a real unit does: mark its own checkboxes in the change's task file."""
        tasks = tree / "openspec/changes/c/tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]"),
                         encoding="utf-8")

    calls = agent_runner(
        '```json\n{"outcome": "GROUP_DONE", "summary": "both tasks done",'
        ' "completed": ["1.1", "1.2"], "notes": "the config lives in set/"}\n```',
        side_effect=did_the_work,
    )
    _lifecycle_project(tmp_path)

    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert code == 0
    assert payload["outcome"] == "GROUP_DONE"
    assert payload["gate"] == "no-gate", "this project declares none, and that is not a pass"
    assert payload["committed"] is True

    record = json.loads(Path(payload["record"]).read_text(encoding="utf-8"))
    assert record["verdict"]["completed"] == ["1.1", "1.2"]
    assert record["diff"]["claimed_but_unmarked"] == []
    assert calls, "the agent session was actually invoked"


def test_the_unit_receives_its_slice_and_the_change_s_artifacts(tmp_path, agent_runner):
    calls = agent_runner('```json\n{"outcome": "PARTIAL", "summary": "some"}\n```')
    _lifecycle_project(tmp_path)
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    prompt = calls[0]["prompt"]
    assert "1.1 alpha" in prompt
    assert "2.1 bravo" not in prompt, "another group's tasks do not travel with the slice"
    assert "proposal.md" in prompt, "the change's own artifacts are on the reading list"
    assert "tasks.md" not in prompt.split("## Read these first")[1].split("##")[0]


def test_an_open_decision_marks_the_task_and_sets_the_unit_aside(tmp_path, agent_runner):
    agent_runner(
        '```json\n{"outcome": "NEEDS_INPUT", "summary": "need a choice",'
        ' "open_decisions": [{"task": "1.1", "question": "Which auth provider?"}]}\n```'
    )
    _lifecycle_project(tmp_path)

    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert code == 0
    assert payload["set_aside"]["kind"] == "human-decision"
    assert payload["set_aside"]["detail"] == "Which auth provider?"
    assert payload["committed"] is False, "a stopped unit does not commit"

    line = [l for l in (tmp_path / "openspec/changes/c/tasks.md").read_text(
        encoding="utf-8").splitlines() if "1.1" in l][0]
    assert line.strip().startswith("- [?]") and "Which auth provider?" in line


def test_an_answer_that_cannot_be_parsed_is_a_reporting_failure_not_an_outcome(
        tmp_path, agent_runner):
    agent_runner("I finished everything, honestly.")
    _lifecycle_project(tmp_path)

    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert code == 6
    assert payload["outcome"] == "FAILED_TO_REPORT"
    assert payload["committed"] is False
    assert any("failed to report" in l for l in payload["lines"]), payload["lines"]


def test_the_lock_is_released_even_when_the_unit_fails_to_report(tmp_path, agent_runner):
    """A tree that stays locked after a failure is a tree nobody can use, and the failure
    that locked it is exactly the case where someone needs to run again."""
    agent_runner("no verdict here")
    _lifecycle_project(tmp_path)
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    from set_workcycle.lock import read_lock

    assert read_lock(tmp_path) is None


def test_a_dry_run_builds_the_slice_and_starts_no_session(tmp_path):
    """No fake runner installed: the suite-wide guard fails this test if a session starts."""
    _lifecycle_project(tmp_path)
    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT, "--dry-run")
    assert code == 6, "no verdict, because no session ran"
    assert any("no session started" in l for l in payload["lines"])


def test_the_previous_run_s_notes_travel_to_the_next_unit(tmp_path, agent_runner):
    calls = agent_runner(
        '```json\n{"outcome": "GROUP_DONE", "summary": "done",'
        ' "completed": ["1.1", "1.2"], "notes": "the config lives in set/, not in .claude/"}\n```'
    )
    _project(tmp_path, "## 1. First\n- [ ] 1.1 a\n\n## 2. Second\n- [ ] 2.1 b\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)

    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    tasks = tmp_path / "openspec/changes/c/tasks.md"
    tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ] 1.1", "- [x] 1.1"),
                     encoding="utf-8")
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    assert len(calls) == 2
    assert "the config lives in set/" in calls[1]["prompt"], (
        "a fresh context forgets a discovery as readily as it forgets noise"
    )


def test_an_answer_releases_its_task_and_reaches_the_next_unit(tmp_path, agent_runner):
    """The end-to-end path task 8.2 names, driven through the command rather than asserted
    per layer: an answer that is merely *recorded* leaves its task marked awaiting forever,
    so the group never becomes runnable and the answer changed nothing."""
    agent_runner(
        '```json\n{"outcome": "NEEDS_INPUT", "summary": "need a choice",'
        ' "open_decisions": [{"task": "1.1", "question": "Which auth provider?"}]}\n```'
    )
    _lifecycle_project(tmp_path)
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    tasks = tmp_path / "openspec/changes/c/tasks.md"
    assert "- [?] 1.1" in tasks.read_text(encoding="utf-8")
    code, blocked = _run(tmp_path, "--change", "c", "status")
    assert "awaiting" in blocked["reasons"]["1"]

    _run(tmp_path, "--change", "c", "answer", "--task", "1.1",
         "--answer", "Use OIDC", "--source", "the surface")

    calls = agent_runner('```json\n{"outcome": "PARTIAL", "summary": "resumed"}\n```')
    code, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    assert code == 0
    assert "- [ ] 1.1" in tasks.read_text(encoding="utf-8"), "the task is no longer awaiting"
    assert "Use OIDC" in calls[-1]["prompt"], (
        "an answer nobody tells the next run about is an answer nobody acted on"
    )


# ── two defects a LIVE run found that every test above had passed ─────────────────────────


def test_an_answer_survives_a_status_call_between_being_written_and_being_used(
        tmp_path, agent_runner):
    """Found live, not here. The test above answered and ran in consecutive commands, so the
    run's own intake carried the answer — a path the user does not take. Interleave one
    `status`, which takes answers in on every path by design, and the answer's TEXT was gone
    by the time a unit ran: the task was released and the unit asked the same question again.

    The user-reachable sequence is answer → look → run. That is what this drives."""
    agent_runner(
        '```json\n{"outcome": "NEEDS_INPUT", "summary": "need a choice",'
        ' "open_decisions": [{"task": "1.1", "question": "Which wording?"}]}\n```'
    )
    _lifecycle_project(tmp_path)
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    _run(tmp_path, "--change", "c", "answer", "--task", "1.1",
         "--answer", "Use OIDC", "--source", "the surface")
    _run(tmp_path, "--change", "c", "status")          # <- the step that used to lose it

    calls = agent_runner('```json\n{"outcome": "PARTIAL", "summary": "resumed"}\n```')
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)
    assert "Use OIDC" in calls[-1]["prompt"], (
        "releasing a task is not the same as delivering the answer"
    )


def test_a_task_an_earlier_run_completed_is_not_reported_as_unmarked(tmp_path, agent_runner):
    """Also found live. The report said 'claimed complete but not marked in the file' about a
    task that WAS marked — by the previous run. A divergence report that states something
    untrue is worse than one that stays quiet: the reader checks it, finds the marker, and
    stops trusting the whole report."""
    def mark_one(tree: Path) -> None:
        tasks = tree / "openspec/changes/c/tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ] 1.1", "- [x] 1.1"),
                         encoding="utf-8")

    agent_runner('```json\n{"outcome": "PARTIAL", "summary": "did the first",'
                 ' "completed": ["1.1"]}\n```', side_effect=mark_one)
    _lifecycle_project(tmp_path)
    _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    agent_runner('```json\n{"outcome": "PARTIAL", "summary": "and again",'
                 ' "completed": ["1.1"]}\n```')
    _, payload = _run(tmp_path, "--change", "c", "run", "--seat", SEAT)

    record = json.loads(Path(payload["record"]).read_text(encoding="utf-8"))
    assert record["diff"]["claimed_but_unmarked"] == [], (
        "1.1 is marked in the file; saying otherwise is false"
    )
    assert any("earlier run had already completed it" in l for l in payload["lines"]), payload["lines"]
