"""What awaits a HUMAN in a project — task 7.14.

The case this guards is the one a fleet screen gets wrong by construction: a
project with no running agent and an open decision renders as a project with
nothing to do. Every test below is about a DISTINCTION the surface would
otherwise collapse.
"""

from __future__ import annotations

import json
import os

from set_orch.fleet.awaiting import Awaiting, awaiting_for, read_awaiting


def _write(tmp_path, changes, **top):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"changes": changes, **top}))
    return str(p)


def test_a_missing_state_file_is_UNMEASURED_not_empty(tmp_path):
    """The false-absence class, at the top of this module's own path. A project
    with no orchestration state has not been asked; reporting `total 0` with no
    marker would state calm that nothing verified.
    """
    a = read_awaiting(str(tmp_path / "nincs-ilyen.json"))
    assert a.source_missing is True
    assert a.total == 0


def test_a_malformed_state_file_does_not_take_the_screen_down(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{ ez nem json")
    a = read_awaiting(str(p))
    assert a.source_missing is True


def test_a_declared_manual_step_is_awaiting_even_while_nothing_runs(tmp_path):
    """`has_manual_tasks` is the planner saying a step no agent can take — an
    API key, an OAuth registration. Nothing is running and nothing will start:
    this is the ordinary shape of stopped work.
    """
    p = _write(tmp_path, [{"name": "checkout", "status": "pending", "has_manual_tasks": True}])
    a = read_awaiting(p)
    assert a.manual == ["checkout"]
    assert a.total == 1


def test_a_merged_change_no_longer_awaits_anybody(tmp_path):
    """Its manual step was done or overtaken. Listing it forever is how a
    counter becomes decoration — and a counter nobody believes is worse than
    no counter, because it also hides the real ones.
    """
    p = _write(tmp_path, [{"name": "checkout", "status": "merged", "has_manual_tasks": True}])
    assert read_awaiting(p).total == 0


def test_a_running_change_with_a_DEAD_pid_is_orphaned(tmp_path):
    """The measured case, and the dangerous one: the state says in flight,
    nothing wrote down that it stopped, and nothing ever will. It reads as work
    in progress forever.
    """
    p = _write(tmp_path, [{"name": "cart", "status": "running", "ralph_pid": 999_999_999}])
    a = read_awaiting(p)
    assert a.orphaned == ["cart"]
    assert a.unverifiable == []


def test_a_running_change_with_a_LIVE_pid_is_unverifiable_never_fine(tmp_path):
    """A pid is not an identity. `os.path.isdir("/proc/N")` answers whether *a*
    process holds that number, not whether YOURS is alive — pids are recycled,
    and a 138-day-old state file's pid says nothing about today.

    So this is neither counted as awaiting (a false alarm) nor reported as
    healthy (a claim). It is named.
    """
    p = _write(tmp_path, [{"name": "cart", "status": "running", "ralph_pid": os.getpid()}])
    a = read_awaiting(p)
    assert a.unverifiable == ["cart"]
    assert a.orphaned == []
    assert a.total == 0, "an admission must not inflate a count a reader acts on"


def test_a_running_change_with_NO_pid_anywhere_is_unverifiable_not_orphaned(tmp_path):
    """"No pid was written down" and "the process is gone" are different facts
    that lead to different actions, and only the second is a finding. Collapsing
    them would report an orphan for every run that predates pid recording.
    """
    p = _write(tmp_path, [{"name": "cart", "status": "running"}])
    a = read_awaiting(p)
    assert a.unverifiable == ["cart"]
    assert a.orphaned == []


def test_the_orchestrator_pid_is_the_fallback_when_the_change_named_none(tmp_path):
    p = _write(
        tmp_path,
        [{"name": "cart", "status": "dispatched"}],
        orchestrator_pid=999_999_999,
    )
    assert read_awaiting(p).orphaned == ["cart"]


def test_stalled_is_reported_as_its_own_kind_not_folded_into_orphaned(tmp_path):
    """Three kinds, three different actions. `stalled` was RECORDED by the
    engine; `orphaned` was MEASURED against a process that is gone. A reader
    chases them differently, so summing them into one "blocked" throws away the
    only thing that says what to do next.
    """
    p = _write(
        tmp_path,
        [
            {"name": "a", "status": "stalled"},
            {"name": "b", "status": "running", "ralph_pid": 999_999_999},
            {"name": "c", "status": "pending", "has_manual_tasks": True},
        ],
    )
    a = read_awaiting(p)
    assert (a.stalled, a.orphaned, a.manual) == (["a"], ["b"], ["c"])
    assert a.total == 3


def test_a_stalled_change_is_not_also_counted_as_in_flight(tmp_path):
    """It would be double-counted otherwise, and a total that exceeds the number
    of changes is the first thing that makes a reader stop trusting the panel.
    """
    p = _write(tmp_path, [{"name": "a", "status": "stalled", "ralph_pid": 999_999_999}])
    a = read_awaiting(p)
    assert a.total == 1
    assert a.orphaned == []


def test_a_change_with_no_name_is_skipped_rather_than_rendered_as_blank(tmp_path):
    p = _write(tmp_path, [{"status": "stalled"}, {"name": "", "status": "stalled"}])
    assert read_awaiting(p).total == 0


def test_the_cache_notices_a_change_that_keeps_the_same_mtime_second(tmp_path):
    """The cache is keyed on mtime AND size. This repository has already paid
    for an invalidation that compared too little — CPython's bytecode cache
    compares mtime and size, and two same-second writes of equal length reused
    a stale artifact. Here the size differs, which is what the second key is for.
    """
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"changes": [{"name": "a", "status": "stalled"}]}))
    first = read_awaiting(str(p))
    assert first.stalled == ["a"]

    os.utime(str(p), (0, 0))
    p.write_text(json.dumps({"changes": [{"name": "a", "status": "stalled"}, {"name": "bb", "status": "stalled"}]}))
    os.utime(str(p), (0, 0))  # same mtime as the first read, different size
    second = read_awaiting(str(p))
    assert second.stalled == ["a", "bb"], "a same-second rewrite was served from a stale parse"


def test_awaiting_for_resolves_by_project_name(tmp_path):
    root = tmp_path / "set-core"
    d = root / "runtime" / "proj" / "orchestration"
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"changes": [{"name": "x", "status": "stalled"}]}))
    a = awaiting_for("proj", data_dir=str(root))
    assert a.stalled == ["x"]


def test_the_payload_shape_carries_source_missing_so_a_zero_can_be_read(tmp_path):
    """A zero and an unmeasured zero must be distinguishable on the wire, or the
    surface cannot tell them apart either.
    """
    empty = Awaiting().as_dict()
    unmeasured = Awaiting(source_missing=True).as_dict()
    assert empty["total"] == unmeasured["total"] == 0
    assert empty["source_missing"] is False and unmeasured["source_missing"] is True
