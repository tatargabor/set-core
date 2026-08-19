"""Task 3.9 — what an agent is working towards, read from the engine's record.

Two things are asserted here that a happy-path suite would not reach: that the
on-disk contract this module duplicates has not drifted from the engine's own
constant, and that a record claiming a live run is checked against the process
rather than believed.
"""

from __future__ import annotations

import json

import pytest

from set_orch.fleet import purpose


# --------------------------------------------------------------------------- #
# the duplicated contract
# --------------------------------------------------------------------------- #


def test_the_run_state_path_still_matches_the_engine_s_own_constant():
    """`set_orch` may not import `set_workcycle`, so the layout is a SECOND COPY.

    A comment saying "keep these in step" asks to be believed. This fails
    instead — and the test may import both because `tests/` is outside the
    dependency scan on purpose (see `test_workcycle_dependency_direction.py`).
    """
    from set_workcycle.engine import RUN_STATE_DIR
    assert purpose.RUN_STATE_REL == RUN_STATE_DIR


def test_orchestration_still_does_not_import_the_engine():
    """The guard that caught an earlier version of this work, asserted here too.

    Held next to the copy it justifies: a reader who finds `RUN_STATE_REL`
    duplicated will ask why, and the answer must be one file away.
    """
    import ast
    from pathlib import Path
    src = Path(purpose.__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith("set_workcycle") for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("set_workcycle")


# --------------------------------------------------------------------------- #
# progress is counted in TASKS
# --------------------------------------------------------------------------- #


def _tasks(tmp_path, change, body):
    d = tmp_path / "openspec" / "changes" / change
    d.mkdir(parents=True)
    (d / "tasks.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_progress_counts_ticked_tasks_and_nothing_else(tmp_path):
    _tasks(tmp_path, "c", """
## 1. Group
- [x] 1.1 done
- [ ] 1.2 open
- [~] 1.3 partial
- [x] AC-4: an acceptance criterion, ticked
- [x] not numbered at all
""")
    p = purpose.read_progress(str(tmp_path), "c")
    assert (p.done, p.total, p.partial) == (1, 3, 1)


def test_a_partial_is_not_rounded_up_to_done(tmp_path):
    """`~` is a claim with a limit in it. Counting it as done reports work that
    is not there — and the limit is exactly what the mark exists to carry."""
    _tasks(tmp_path, "c", "- [~] 1.1 partial\n- [~] 1.2 partial\n")
    p = purpose.read_progress(str(tmp_path), "c")
    assert p.done == 0 and p.partial == 2 and p.fraction == 0.0


def test_a_bare_bracket_pattern_would_have_counted_the_criteria(tmp_path):
    """Held so a 'simplification' to `^- \\[` fails here instead of inflating.

    Measured on this repository: the numbered pattern gives 93 and the bare one
    215, because acceptance criteria wear the same shape. The number is what
    makes a line a task.
    """
    body = "- [x] 1.1 task\n" + "".join(f"- [x] AC-{i}: criterion\n" for i in range(20))
    _tasks(tmp_path, "c", body)
    assert purpose.read_progress(str(tmp_path), "c").total == 1
    naive = sum(1 for line in body.splitlines() if line.startswith("- ["))
    assert naive == 21                      # what the wrong pattern would say


def test_an_unreadable_task_file_is_not_zero_progress(tmp_path):
    """A zero with `measured: false` says *we looked nowhere*; a zero with
    `measured: true` says *nothing is done*. Rendering them alike is the
    false-absence class."""
    p = purpose.read_progress(str(tmp_path), "nincs-ilyen")
    assert p.measured is False and p.done == 0
    assert p.fraction is None, "an unmeasured change must not draw a progress bar at 0%"


# --------------------------------------------------------------------------- #
# a record is not a run
# --------------------------------------------------------------------------- #


def _record(tmp_path, change, unit, **over):
    d = tmp_path / "set" / "runtime" / "work-cycle" / change
    d.mkdir(parents=True, exist_ok=True)
    rec = {"unit_id": unit, "change": change, "group": "g1", "kind": "slice",
           "lens": None, "seat": "proj#aaaa", "pid": 0, "started_at": "2026-08-19T10:00:00+02:00",
           "verdict": None, "commit": None, "set_aside": None}
    rec.update(over)
    (d / f"{unit}.json").write_text(json.dumps(rec), encoding="utf-8")
    return tmp_path


def _proc(tmp_path, pid, comm="claude"):
    d = tmp_path / "proc" / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "comm").write_text(comm + "\n")
    return str(tmp_path / "proc")


def test_a_record_whose_process_is_gone_is_stale(tmp_path):
    """The shape 7.14 found on real data: 68 days of 'in progress' that was not."""
    _record(tmp_path, "c", "u1", pid=999999)
    proc = _proc(tmp_path, 1)                       # 999999 is deliberately absent
    [p] = purpose.read_purposes(str(tmp_path), proc_root=proc)
    assert p.status == "stale"


def test_a_committed_run_is_finished_whatever_its_pid_now_is(tmp_path):
    """Asked in this order on purpose: a finished run's process is always gone,
    so checking the pid first would call every completed run stale."""
    _record(tmp_path, "c", "u1", pid=999999, commit={"committed": True, "sha": "abc"})
    [p] = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 1))
    assert p.status == "finished"


def test_a_live_pid_that_is_not_an_agent_is_reported_as_unverified(tmp_path):
    """A pid is recycled. "A process holds that number" is not "your run is
    alive" — so the answer says which question it answered."""
    _record(tmp_path, "c", "u1", pid=4242)
    proc = _proc(tmp_path, 4242, comm="gedit")
    [p] = purpose.read_purposes(str(tmp_path), proc_root=proc)
    assert p.status == "running" and p.pid_unverified is True


def test_a_live_agent_pid_is_verified(tmp_path):
    _record(tmp_path, "c", "u1", pid=4242)
    [p] = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 4242))
    assert p.status == "running" and p.pid_unverified is False


def test_no_record_means_no_purpose_rather_than_an_empty_one(tmp_path):
    """Design §8.1 — where the engine is absent the capability is absent and the
    absence is stated. For a while that is every machine."""
    assert purpose.read_purposes(str(tmp_path)) == []


def test_an_unreadable_record_is_named_and_the_rest_still_read(tmp_path):
    _record(tmp_path, "c", "u1", pid=4242)
    bad = tmp_path / "set" / "runtime" / "work-cycle" / "c" / "broken.json"
    bad.write_text("{ nem json", encoding="utf-8")
    got = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 4242))
    assert [p.unit_id for p in got] == ["u1"]


def test_a_stale_record_never_lends_its_purpose_to_a_live_pid(tmp_path):
    """The join is the engine's recorded pid, and a recycled number must not
    make one project's work appear under another's agent."""
    _record(tmp_path, "c", "u1", pid=4242, commit={"committed": True})
    got = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 4242))
    assert purpose.purpose_for_pid(got, 4242) is None


def test_the_purpose_of_a_live_run_is_found_by_pid(tmp_path):
    _record(tmp_path, "c", "u1", pid=4242, group="gate-layer")
    got = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 4242))
    p = purpose.purpose_for_pid(got, 4242)
    assert p is not None and p.group == "gate-layer" and p.change == "c"


def test_progress_travels_with_the_purpose(tmp_path):
    _record(tmp_path, "c", "u1", pid=4242)
    _tasks(tmp_path, "c", "- [x] 1.1 a\n- [ ] 1.2 b\n- [ ] 1.3 c\n")
    [p] = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 4242))
    assert p.progress.done == 1 and p.progress.total == 3
    assert abs((p.progress.fraction or 0) - 1 / 3) < 1e-9


def test_the_verdict_is_carried_verbatim_rather_than_summarised(tmp_path):
    """A summary of a verdict is a second judgement, made by the wrong layer."""
    verdict = {"outcome": "changes-requested", "tasks": ["1.1"], "note": "a gate failed"}
    _record(tmp_path, "c", "u1", pid=4242, verdict=verdict)
    [p] = purpose.read_purposes(str(tmp_path), proc_root=_proc(tmp_path, 4242))
    assert p.verdict == verdict
