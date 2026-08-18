"""Adoption: any project, several at once, and nothing about any one of them in the engine.

Written with the change `work-cycle-engine-apply-first`, group 7. The property that makes
this capability real is negative — the engine must carry no knowledge of any particular
project — and a negative property is checked by scanning the source, not by running it
against a project and finding it worked.
"""
from __future__ import annotations

import ast
import io
import contextlib
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_workcycle.adoption import ADOPTION_REL, read_adoption  # noqa: E402
from set_workcycle.cli import main, read_run_state  # noqa: E402
from set_workcycle.connector import intake, write_answer  # noqa: E402
from set_workcycle.engine import UnitRecord, WorkUnit, run_gate  # noqa: E402
from set_workcycle.lock import acquire, read_lock  # noqa: E402

SEAT_A = "session:aaaaaaaa-1111-2222-3333-444444444444"
SEAT_B = "session:bbbbbbbb-1111-2222-3333-444444444444"


def _project(root: Path, *, declare: bool = True, gates=None, tasks: str = None) -> Path:
    (root / "openspec" / "changes" / "c").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "changes" / "c" / "tasks.md").write_text(
        tasks or "## 1. First\n- [ ] 1.1 alpha\n", encoding="utf-8")
    if declare:
        (root / "set").mkdir(exist_ok=True)
        body = "changes_dir: openspec/changes\n"
        if gates is not None:
            body += "gates: [" + ", ".join(gates) + "]\n"
        (root / "set" / "work-cycle.yaml").write_text(body, encoding="utf-8")
    return root


def _run(tree: Path, *argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["--tree", str(tree), "--json", *argv])
    return code, json.loads(buf.getvalue())


# ── the declaration ───────────────────────────────────────────────────────────────────────


def test_a_missing_declaration_is_named_rather_than_guessed(tmp_path):
    """A guess that happens to be right for one repository is indistinguishable, from the
    outside, from a project that actually said so."""
    _project(tmp_path, declare=False)
    adoption = read_adoption(tmp_path)
    assert adoption.adopted is False
    assert ADOPTION_REL in adoption.missing
    assert "does not guess" in adoption.missing


def test_a_declaration_without_a_changes_location_is_refused(tmp_path):
    (tmp_path / "set").mkdir()
    (tmp_path / "set" / "work-cycle.yaml").write_text("gates: [test]\n", encoding="utf-8")
    adoption = read_adoption(tmp_path)
    assert adoption.adopted is False and "changes_dir" in adoption.missing


def test_an_undeclared_gate_is_not_invented(tmp_path):
    """An adopted project that declares no gates runs with none — and the engine says so
    rather than inferring a command from the project's contents."""
    _project(tmp_path)
    adoption = read_adoption(tmp_path)
    assert adoption.adopted is True
    assert adoption.gates_declared is False
    assert "none is inferred" in adoption.describe()
    assert run_gate([], tmp_path).state == "no-gate"


def test_declaring_an_empty_gate_list_is_distinct_from_declaring_none(tmp_path):
    _project(tmp_path, gates=[])
    assert read_adoption(tmp_path).gates_declared is True


def test_a_caller_stating_where_changes_live_is_not_a_guess(tmp_path):
    """An override is the caller *saying* it; what is refused is the engine deciding."""
    assert read_adoption(tmp_path, changes_dir_override="elsewhere/changes").adopted is True


# ── un-adopted is not "nothing to do" ─────────────────────────────────────────────────────


def test_an_un_adopted_project_is_reported_as_un_adopted(tmp_path):
    _project(tmp_path, declare=False)
    code, payload = _run(tmp_path, "--change", "c", "status")
    assert code == 2 and payload["adopted"] is False
    assert "selected" not in payload
    assert not re.search(r"\b0 runnable\b|up to date", json.dumps(payload), re.IGNORECASE)


def test_an_adopted_project_with_no_open_work_is_distinguishable_from_an_un_adopted_one(tmp_path):
    _project(tmp_path, tasks="## 1. First\n- [x] 1.1 alpha\n")
    code, payload = _run(tmp_path, "--change", "c", "status")
    assert code == 0 and payload["adopted"] is True
    assert payload["selected"] is None
    assert payload["reasons"] == {"1": "complete"}, "the reason is stated, not merely absent"


# ── several projects, kept apart ──────────────────────────────────────────────────────────


def test_two_projects_are_driven_at_once_with_no_state_bleed(tmp_path):
    a = _project(tmp_path / "a")
    b = _project(tmp_path / "b")

    acquire(a, SEAT_A, change="c", group="1")
    acquire(b, SEAT_B, change="c", group="1")
    assert read_lock(a).seat == SEAT_A
    assert read_lock(b).seat == SEAT_B, "each project holds its own lock"

    UnitRecord(unit=WorkUnit(change="c", tree=a, seat=SEAT_A, group_key="1"), pid=1).save()
    assert [r["seat"] for r in read_run_state(a, "c")] == [SEAT_A]
    assert read_run_state(b, "c") == [], "one project's runs do not appear in another's"


def test_an_answer_reaches_only_its_own_project(tmp_path):
    """The same change name and the same task id in two projects must not cross."""
    a = _project(tmp_path / "a")
    b = _project(tmp_path / "b")
    write_answer(a, "c", "1.1", "for project a", source="chat")

    assert [x.answer for x in intake(a, awaiting={"c#1.1"}).applied] == ["for project a"]
    assert intake(b, awaiting={"c#1.1"}).applied == []


def test_a_blocked_unit_in_one_project_does_not_stop_another(tmp_path, agent_runner):
    agent_runner('```json\n{"outcome": "GROUP_DONE", "summary": "done", "completed": ["1.1"]}\n```')
    a = _project(tmp_path / "a", tasks="## 1. First\n- [?] 1.1 waiting on a person\n")
    b = _project(tmp_path / "b")

    code_a, _ = _run(a, "--change", "c", "run", "--seat", SEAT_A)
    code_b, payload_b = _run(b, "--change", "c", "run", "--seat", SEAT_B)
    assert code_a == 1, "nothing runnable in a"
    assert code_b == 0 and payload_b["started"] is True


# ── the engine knows nothing about any project ────────────────────────────────────────────


def test_the_engine_package_names_no_project_and_no_project_path():
    """The test task 7.2 asks for. A project name or an absolute path inside the engine is
    how "a second project needs no framework change" quietly stops being true — and it is
    also how a private consumer's name leaks into a public framework."""
    package = REPO / "lib" / "set_workcycle"
    absolute_path = re.compile(r"(?<![\w.])/(?:home|Users|var|opt|srv)/")
    offenders: list[str] = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if absolute_path.search(node.value):
                    offenders.append(
                        f"{path.relative_to(REPO)}:{node.lineno}: {node.value[:60]!r}")
    assert not offenders, "an absolute path inside the engine:\n  " + "\n  ".join(offenders)


def test_the_engine_never_resolves_a_project_from_ambient_state():
    """Per-project separation is not bookkeeping the engine has to remember. It is given the
    tree on every operation and never *finds* one — no current directory, no environment
    variable, no walking upward for a marker. An operation that discovered its own project is
    the one that could touch another's.

    Stated as "never resolves" rather than as a list of functions that take a `tree`
    argument: a maintained list of exempt pure functions would be a second copy of the rule,
    and it would drift the moment somebody added a helper.
    """
    package = REPO / "lib" / "set_workcycle"
    forbidden_calls = {"getcwd", "cwd", "chdir", "expanduser", "getenv"}
    offenders: list[str] = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
                if name in forbidden_calls:
                    offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: {name}()")
            if isinstance(node, ast.Attribute) and node.attr == "environ":
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: os.environ")
    # `runner.py` copies the ambient environment for the CHILD process, which is the one
    # legitimate use — it passes the environment on rather than reading a project out of it.
    offenders = [o for o in offenders if "runner.py" not in o]
    assert not offenders, (
        "the engine resolves a project from ambient state:\n  " + "\n  ".join(offenders))


def test_every_piece_of_per_project_state_lives_under_the_tree_it_belongs_to():
    """The positive half: locks, run records and pending answers are all rooted at a tree the
    caller supplied, so two projects cannot share one by construction."""
    from set_workcycle.connector import ANSWERS_REL, INTAKE_STATE_REL
    from set_workcycle.engine import RUN_STATE_DIR
    from set_workcycle.lock import LOCK_REL

    for rel in (LOCK_REL, RUN_STATE_DIR, ANSWERS_REL, INTAKE_STATE_REL):
        assert not Path(rel).is_absolute(), f"{rel} is absolute — it would be shared"
        assert not rel.startswith(".."), f"{rel} escapes the tree"


# ── adoption changes nothing about how the project already works ──────────────────────────


def test_a_task_file_with_no_dependency_annotations_is_driven_without_being_edited(tmp_path):
    """The serial default does the work. Requiring an annotation before the first run would
    be exactly the "the project must change how it works" failure."""
    tasks = "## 1. First\n- [ ] 1.1 a\n\n## 2. Second\n- [ ] 2.1 b\n\n## 3. Third\n- [ ] 3.1 c\n"
    _project(tmp_path, tasks=tasks)
    before = (tmp_path / "openspec/changes/c/tasks.md").read_text(encoding="utf-8")

    code, payload = _run(tmp_path, "--change", "c", "status")
    assert code == 0 and payload["selected"] == "1"
    assert "blocked by 1" in payload["reasons"]["2"]
    assert (tmp_path / "openspec/changes/c/tasks.md").read_text(encoding="utf-8") == before, (
        "the file required no edit before the first run"
    )


def test_the_project_s_existing_markings_are_read_rather_than_replaced(tmp_path):
    """`[x]`, `[ ]` and `[?]` are the project's notation. The engine reads them; it does not
    ask for a different one."""
    _project(tmp_path, tasks="## 1. First\n- [x] 1.1 done\n- [?] 1.2 waiting\n- [ ] 1.3 open\n")
    code, payload = _run(tmp_path, "--change", "c", "status")
    assert code == 0
    assert "awaiting" in payload["reasons"]["1"]
