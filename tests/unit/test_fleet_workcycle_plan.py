"""What the engine says is runnable, read across the D10 seam.

The load-bearing test here is `test_runnable_is_derived_from_the_key_the_engine
_actually_emits`. It guards a defect that shipped for about ten minutes during
this change and would have been invisible: the view read `payload["runnable"]`,
a key `cmd_status` has never written, so every change on the machine reported
*not runnable* while looking exactly like a measurement.
"""

from __future__ import annotations

import subprocess

import pytest

from set_orch.fleet import workcycle_plan as plan


@pytest.fixture(autouse=True)
def _clear():
    plan.clear_cache()
    yield
    plan.clear_cache()


def test_the_engine_command_name_matches_the_one_the_route_builds():
    """SECOND COPY, guarded — a comment asking to keep them in step asks to be believed."""
    from set_orch.api import fleet as fleet_api
    assert plan.ENGINE_COMMAND == fleet_api.ENGINE_COMMAND


def test_runnable_is_derived_from_the_key_the_engine_actually_emits():
    """Read against the engine's own `cmd_status` payload, not against a guess."""
    got = plan.read_plan("/tmp", "c", runner=lambda a: (
        0, '{"adopted": true, "selected": "2", "reasons": {}}', ""))
    assert got.runnable is True
    assert got.selected == "2"

    plan.clear_cache()
    got = plan.read_plan("/tmp", "c", runner=lambda a: (
        1, '{"adopted": true, "selected": null, "reasons": {"1": "blocked by 0"}}', ""))
    assert got.runnable is False
    assert got.payload["reasons"] == {"1": "blocked by 0"}


def test_a_field_the_engine_does_not_write_is_not_invented():
    """The refuted pattern, held as a test rather than as a memory.

    `runnable` is not a key of the engine's answer. If somebody reintroduces a
    direct read of one, this fails — because the engine's payload here has no
    such key and the view must still say True.
    """
    got = plan.read_plan("/tmp", "c", runner=lambda a: (0, '{"adopted": true, "selected": "1"}', ""))
    assert "runnable" not in got.payload
    assert got.runnable is True


def test_an_unadopted_project_reports_neither_runnable_nor_not_runnable():
    got = plan.read_plan("/tmp", "c", runner=lambda a: (
        2, '{"adopted": false, "missing": "set/work-cycle.yaml"}', ""))
    # exit 2 is the engine REFUSING, so it is carried as its words …
    assert got.available is False
    assert "work-cycle.yaml" in got.reason
    # … and `runnable` is unknown, never False.
    assert got.runnable is None


def test_a_missing_engine_is_an_answer_not_an_empty_screen():
    got = plan.read_plan("/tmp", "c",
                         runner=lambda a: (_ for _ in ()).throw(FileNotFoundError()))
    assert got.available is False
    assert got.runnable is None
    assert "not installed" in got.reason
    assert "recorded runs are still shown" in got.reason


def test_a_timeout_is_not_cached_because_it_is_a_fact_about_this_moment():
    calls = []

    def timing_out(argv):
        calls.append(argv)
        raise subprocess.TimeoutExpired(argv, 1)

    for _ in range(2):
        got = plan.read_plan("/tmp", "c", runner=timing_out)
        assert got.available is False and got.runnable is None
    assert len(calls) == 2, "a timeout was cached and kept answering after the cause"


def test_the_answer_is_cached_on_what_would_change_it(tmp_path):
    """A start, a finish, or an edit invalidates it — nobody has to remember to."""
    changes = tmp_path / "openspec" / "changes" / "c"
    changes.mkdir(parents=True)
    tasks = changes / "tasks.md"
    tasks.write_text("## 1. g\n\n- [ ] 1.1 a\n")

    calls = []

    def counting(argv):
        calls.append(argv)
        return 0, '{"adopted": true, "selected": "1"}', ""

    plan.read_plan(str(tmp_path), "c", runner=counting)
    plan.read_plan(str(tmp_path), "c", runner=counting)
    assert len(calls) == 1, "a poll spawned a process per call"

    # An edit changes the answer, so it changes the key. ⚠ Ticking a checkbox
    # leaves the SIZE identical and can land inside the filesystem's timestamp
    # granularity — measured here — so this is the case an `(mtime, size)` key
    # misses while looking like it works.
    assert len(tasks.read_text()) == len("## 1. g\n\n- [x] 1.1 a\n")
    tasks.write_text("## 1. g\n\n- [x] 1.1 a\n")
    plan.read_plan(str(tmp_path), "c", runner=counting)
    assert len(calls) == 2

    # So does a run appearing — the directory's own stamp is in the fingerprint.
    runs = tmp_path / "set" / "runtime" / "work-cycle" / "c"
    runs.mkdir(parents=True)
    plan.read_plan(str(tmp_path), "c", runner=counting)
    assert len(calls) == 3


def test_the_argv_this_builds_parses_with_the_engine_s_own_parser():
    """The result, not the mechanism.

    Every other test here injects a runner, so every one of them passed while the
    argv this module built would have died on `unrecognized arguments: --json` —
    `--json` is a top-level flag and must precede the subcommand. Asking the
    engine's real parser is the only check that could see that.
    """
    from set_workcycle.cli import build_parser

    seen = {}
    plan.read_plan("/tmp", "c", runner=lambda a: seen.setdefault("argv", a) and (0, "{}", ""))
    argv = seen["argv"]
    assert argv[0] == plan.ENGINE_COMMAND

    parsed = build_parser().parse_args(argv[1:])
    assert parsed.json is True
    assert parsed.tree == "/tmp"
    assert parsed.change == "c"
    assert parsed.func.__name__ == "cmd_status"


def test_a_whole_tree_query_names_no_change_at_all():
    """Not an empty `--change`: absence is how the engine is asked about the tree."""
    from set_workcycle.cli import build_parser

    seen = {}
    plan.read_plan("/tmp", "", runner=lambda a: seen.setdefault("argv", a) and (0, "{}", ""))
    assert "--change" not in seen["argv"]
    assert build_parser().parse_args(seen["argv"][1:]).change == ""
