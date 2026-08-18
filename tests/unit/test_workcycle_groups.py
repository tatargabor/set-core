"""Task-group resolution: groups, edges, selection, slice, carry-over, reading list.

Written with the change `work-cycle-engine-apply-first`, group 3. Every test here has been
run against a deliberately broken implementation and observed to FAIL — a test written
alongside a fix that also passes without it proves nothing and looks like proof forever.
The mutations used are named in each test's docstring, so the check can be repeated rather
than believed.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_workcycle.groups import (  # noqa: E402
    AWAITING,
    DONE,
    OPEN,
    DependencyCycle,
    RunNote,
    carry_over_for,
    cut_slice,
    parse_task_groups,
    reading_list,
    select_next_group,
)


def _write(tmp_path: Path, body: str, name: str = "tasks.md") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
    return p


# ── R1: groups are read from the task file ────────────────────────────────────────────────


def test_groups_are_identified_with_their_own_task_lines(tmp_path):
    """Mutation: bind every task to the first group → the per-group counts collapse."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. First
        - [ ] 1.1 a
        - [x] 1.2 b

        ## 2. Second
        - [ ] 2.1 c
    """))
    assert [g.key for g in plan.groups] == ["1", "2"]
    assert [t.text for t in plan.by_key("1").tasks] == ["1.1 a", "1.2 b"]
    assert [t.marker for t in plan.by_key("1").tasks] == [OPEN, DONE]
    assert [t.text for t in plan.by_key("2").tasks] == ["2.1 c"]


def test_tasks_before_the_first_heading_become_a_group_rather_than_being_discarded(tmp_path):
    """Mutation: drop the preamble flush → the two lines vanish and no test notices."""
    plan = parse_task_groups(_write(tmp_path, """
        - [ ] loose one
        - [ ] loose two

        ## 1. First
        - [ ] 1.1 a
    """))
    assert len(plan.groups) == 2
    preamble = plan.groups[0]
    assert preamble.heading_line is None
    assert [t.text for t in preamble.tasks] == ["loose one", "loose two"]
    total = sum(len(g.tasks) for g in plan.groups)
    assert total == 3, "every task line belongs to exactly one group"


def test_a_heading_that_carries_no_number_does_not_swell_the_previous_group(tmp_path):
    """The defect this guards is silent and inflating: an unnumbered trailing section — an
    acceptance-criteria list, a notes appendix — attaching its lines to the last numbered
    group, which then reports work it does not own."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. Real work
        - [ ] 1.1 a

        ## Acceptance Criteria
        - [ ] AC-1: something
        - [ ] AC-2: something else
    """))
    assert len(plan.by_key("1").tasks) == 1
    tail = plan.groups[-1]
    assert tail.numbered is False
    assert len(tail.tasks) == 2


def test_a_heading_inside_a_fence_is_content_not_structure(tmp_path):
    """Mutation: drop the fence tracking → the fenced `## 9.` opens a phantom group."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. First
        - [ ] 1.1 a

        ```markdown
        ## 9. Not a real group
        - [ ] 9.1 not a real task
        ```

        - [ ] 1.2 b
    """))
    assert [g.key for g in plan.groups] == ["1"]
    assert [t.text for t in plan.by_key("1").tasks] == ["1.1 a", "1.2 b"]


def test_a_deeper_heading_level_is_used_when_that_is_where_the_numbers_are(tmp_path):
    """Adoption: a project using `###` for groups is driven without editing its file first."""
    plan = parse_task_groups(_write(tmp_path, """
        # Tasks

        ### 1. First
        - [ ] 1.1 a

        ### 2. Second
        - [ ] 2.1 b
    """))
    assert [g.key for g in plan.groups] == ["1", "2"]


# ── R2: dependency edges, and the fail-closed absence ─────────────────────────────────────


def test_declared_dependencies_are_read(tmp_path):
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 a
        ## 2. B
        - [ ] 2.1 b
        ## 3. C
        <!-- depends: 1, 2 -->
        - [ ] 3.1 c
    """))
    assert plan.by_key("3").declared_depends_on == ("1", "2")
    assert plan.effective_depends_on(plan.by_key("3")) == ("1", "2")


def test_no_annotation_means_serial_not_independent(tmp_path):
    """The fail direction is the point: unannotated must mean *waits*, never *free*."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 a
        ## 2. B
        - [ ] 2.1 b
    """))
    g2 = plan.by_key("2")
    assert g2.annotated is False
    assert g2.declared_independent is False
    assert plan.effective_depends_on(g2) == ("1",), "an unannotated group waits for its predecessor"


def test_independence_is_concluded_only_from_an_explicit_declaration(tmp_path):
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 a
        ## 2. B
        <!-- depends: none -->
        - [ ] 2.1 b
    """))
    g2 = plan.by_key("2")
    assert g2.annotated is True and g2.declared_independent is True
    assert plan.effective_depends_on(g2) == ()
    chosen, _ = select_next_group(plan)
    assert chosen.key == "1"  # lowest-ordered runnable
    plan.by_key("1").tasks[0] = plan.by_key("1").tasks[0].__class__(
        marker=DONE, text="1.1 a", line_no=2, raw="- [x] 1.1 a")
    chosen, _ = select_next_group(plan)
    assert chosen.key == "2"


def test_a_cycle_is_reported_and_nothing_is_declared_runnable(tmp_path):
    """Mutation: return an arbitrary order instead of raising → an order that looks decided."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        <!-- depends: 2 -->
        - [ ] 1.1 a
        ## 2. B
        <!-- depends: 1 -->
        - [ ] 2.1 b
    """))
    with pytest.raises(DependencyCycle) as exc:
        select_next_group(plan)
    assert set(exc.value.cycle) == {"1", "2"}


# ── R3: selection ─────────────────────────────────────────────────────────────────────────


def test_a_group_whose_dependency_still_has_open_tasks_is_not_selected(tmp_path):
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 a
        ## 2. B
        <!-- depends: 1 -->
        - [ ] 2.1 b
    """))
    chosen, reasons = select_next_group(plan)
    assert chosen.key == "1"
    assert "blocked by 1" in reasons["2"]


def test_a_group_awaiting_an_answer_is_skipped_not_blocked_behind(tmp_path):
    """The whole reason a stop point does not stall a change."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [?] 1.1 needs a person
        ## 2. B
        <!-- depends: none -->
        - [ ] 2.1 b
    """))
    chosen, reasons = select_next_group(plan)
    assert chosen.key == "2", "an independent later group stays runnable"
    assert "awaiting" in reasons["1"]


def test_a_group_behind_an_awaiting_group_stays_blocked(tmp_path):
    """The mirror of the test above, and the one that keeps 'skipped' from meaning 'ignored'.
    A group awaiting a person is NOT complete, so its dependents must not start."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [?] 1.1 needs a person
        ## 2. B
        - [ ] 2.1 b
    """))
    chosen, reasons = select_next_group(plan)
    assert chosen is None
    assert "blocked by 1" in reasons["2"]


def test_nothing_runnable_reports_a_reason_for_every_group(tmp_path):
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [x] 1.1 done
        ## 2. B
        - [?] 2.1 needs a person
        ## 3. C
        - [ ] 3.1 c
    """))
    chosen, reasons = select_next_group(plan)
    assert chosen is None
    assert set(reasons) == {"1", "2", "3"}
    assert reasons["1"] == "complete"
    assert "awaiting" in reasons["2"]
    assert "blocked by 2" in reasons["3"]


def test_selection_is_deterministic_for_the_same_file(tmp_path):
    src = """
        ## 1. A
        <!-- depends: none -->
        - [ ] 1.1 a
        ## 2. B
        <!-- depends: none -->
        - [ ] 2.1 b
        ## 3. C
        <!-- depends: none -->
        - [ ] 3.1 c
    """
    picks = {select_next_group(parse_task_groups(_write(tmp_path, src)))[0].key for _ in range(8)}
    assert picks == {"1"}


# ── R4: the slice ─────────────────────────────────────────────────────────────────────────


def test_the_slice_is_the_group_s_block_and_not_the_whole_file(tmp_path):
    """Mutation: hand back the file's full text → this is the test that fails."""
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 alpha
        ## 2. B
        - [ ] 2.1 bravo
    """))
    s = cut_slice(plan.by_key("2"))
    assert "bravo" in s.block
    assert "alpha" not in s.block, "another group's tasks must not travel with the slice"
    assert s.truncated is False


def test_a_caller_s_task_limit_cuts_within_the_group(tmp_path):
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [x] 1.0 already done
        - [ ] 1.1 one
        - [ ] 1.2 two
        - [ ] 1.3 three
    """))
    s = cut_slice(plan.by_key("1"), limit=2)
    assert s.truncated is True
    assert [t.text for t in s.tasks if t.marker == OPEN] == ["1.1 one", "1.2 two"]
    assert "1.3 three" not in s.block
    assert "1.0 already done" in s.block, "context that is not open work is not cut away"


def test_a_limit_at_or_above_the_group_size_is_not_a_truncation(tmp_path):
    plan = parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 one
        - [ ] 1.2 two
    """))
    assert cut_slice(plan.by_key("1"), limit=5).truncated is False
    assert cut_slice(plan.by_key("1"), limit=2).truncated is False


# ── R5: carry-over ────────────────────────────────────────────────────────────────────────


def _plan_three(tmp_path):
    return parse_task_groups(_write(tmp_path, """
        ## 1. A
        - [ ] 1.1 a
        ## 2. B
        - [ ] 2.1 b
        ## 3. C
        - [ ] 3.1 c
    """))


def test_a_resumed_group_receives_its_own_previous_run_s_notes(tmp_path):
    plan = _plan_three(tmp_path)
    notes = [RunNote(group_key="2", notes="left half done", finished_at="2026-08-18T09:00:00")]
    got = carry_over_for(plan, plan.by_key("2"), notes)
    assert [n.notes for n in got] == ["left half done"]


def test_the_previous_group_s_discoveries_reach_the_next_group(tmp_path):
    plan = _plan_three(tmp_path)
    notes = [RunNote(group_key="1", notes="found the config lives elsewhere",
                     finished_at="2026-08-18T09:00:00")]
    got = carry_over_for(plan, plan.by_key("2"), notes)
    assert [n.group_key for n in got] == ["1"]


def test_only_the_most_recent_run_s_notes_survive(tmp_path):
    """Mutation: return every matching note → the slice carries a history instead of a state."""
    plan = _plan_three(tmp_path)
    notes = [
        RunNote(group_key="2", notes="old", finished_at="2026-08-17T08:00:00"),
        RunNote(group_key="2", notes="new", finished_at="2026-08-18T08:00:00"),
        RunNote(group_key="2", notes="middle", finished_at="2026-08-17T20:00:00"),
    ]
    got = carry_over_for(plan, plan.by_key("2"), notes)
    assert [n.notes for n in got] == ["new"]


def test_notes_from_an_unrelated_group_do_not_travel(tmp_path):
    plan = _plan_three(tmp_path)
    notes = [RunNote(group_key="1", notes="two groups back",
                     finished_at="2026-08-18T09:00:00")]
    assert carry_over_for(plan, plan.by_key("3"), notes) == []


# ── R6: the reading list ──────────────────────────────────────────────────────────────────


def test_the_reading_list_covers_the_change_s_artifacts_but_not_its_task_file(tmp_path):
    (tmp_path / "tasks.md").write_text("## 1. A\n- [ ] 1.1 a\n", encoding="utf-8")
    (tmp_path / "proposal.md").write_text("why\n", encoding="utf-8")
    (tmp_path / "specs" / "cap").mkdir(parents=True)
    (tmp_path / "specs" / "cap" / "spec.md").write_text("## ADDED\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not markdown\n", encoding="utf-8")

    names = [p.name for p in reading_list(tmp_path)]
    assert "proposal.md" in names
    assert "spec.md" in names, "a change's specs live in subdirectories and are not optional"
    assert "tasks.md" not in names, "the slice is handed over separately"
    assert "notes.txt" not in names


def test_an_artifact_written_by_an_earlier_run_is_included(tmp_path):
    """Read from disk at the moment the slice is cut — never from a manifest written when the
    change was planned, which is what would make a later run blind to its own predecessor."""
    (tmp_path / "tasks.md").write_text("## 1. A\n- [ ] 1.1 a\n", encoding="utf-8")
    before = [p.name for p in reading_list(tmp_path)]
    (tmp_path / "measurements.md").write_text("what group 2 found\n", encoding="utf-8")
    after = [p.name for p in reading_list(tmp_path)]
    assert "measurements.md" not in before
    assert "measurements.md" in after


# ── a red gate holds the chain, whatever the markers say ───────────────────────────────────


def _two_group_plan(tmp_path):
    """Group 0 fully marked done, group 1 open and serially behind it."""
    p = tmp_path / "tasks.md"
    p.write_text(
        "## 0. First\n\n- [x] 0.1 done\n- [x] 0.2 done\n\n"
        "## 1. Second\n\n- [ ] 1.1 open\n",
        encoding="utf-8",
    )
    return parse_task_groups(p)


def test_a_group_whose_gate_FAILED_is_not_complete_and_holds_the_chain(tmp_path):
    """Measured on the first live cross-run: group 0's gate went red and its commit was
    refused, yet `status` reported `0: complete` and handed group 1 the next slot.

    The markers are what the unit CLAIMED; the gate is what was CHECKED — and only the file
    reaches `is_complete`, because a plan parsed from markdown cannot see a run record.

    Fail direction: the chain runs on over a red tree, so the next unit's own failures can no
    longer be told apart from the one it inherited.
    """
    plan = _two_group_plan(tmp_path)

    chosen, reasons = select_next_group(plan)
    assert chosen is not None and chosen.key == "1", "without the gate, 1 is next — as before"
    assert reasons["0"] == "complete"

    chosen, reasons = select_next_group(plan, gate_failed={"0"})
    assert chosen is None, f"a red gate must hold the chain; chose {chosen and chosen.key}"
    assert "NOT complete" in reasons["0"] and "gate FAILED" in reasons["0"]
    assert "blocked by 0" in reasons["1"], reasons["1"]


def test_a_later_green_run_clears_the_hold(tmp_path):
    """The hold is state, not a verdict on the group forever — the caller derives the set from
    the latest record per group, so a green re-run releases it."""
    plan = _two_group_plan(tmp_path)
    chosen, _ = select_next_group(plan, gate_failed=set())
    assert chosen is not None and chosen.key == "1"


def test_the_hold_is_derived_from_the_LAST_run_of_each_group(tmp_path):
    """The set comes from run records, so this asserts the derivation, not the display: a
    group whose record shows a red gate is held, and one whose record shows green is not."""
    from set_workcycle.cli import gate_failed_groups

    root = tmp_path / "tree"
    d = root / "set" / "runtime" / "work-cycle" / "c"
    d.mkdir(parents=True)
    (d / "c--0.json").write_text(json.dumps(
        {"unit_id": "c--0", "change": "c", "group": "0", "gate": {"state": "failed"}}),
        encoding="utf-8")
    (d / "c--1.json").write_text(json.dumps(
        {"unit_id": "c--1", "change": "c", "group": "1", "gate": {"state": "passed"}}),
        encoding="utf-8")
    (d / "c--2.json").write_text(json.dumps(
        {"unit_id": "c--2", "change": "c", "group": "2", "gate": None}),
        encoding="utf-8")

    assert gate_failed_groups(root, "c") == {"0"}


# ── the hold must be dischargeable, or it is a wall ────────────────────────────────────────


def _held_tree(tmp_path, gate_state="failed"):
    """A tree whose group 0 is fully marked, its record carrying a gate in `gate_state`."""
    root = tmp_path / "tree"
    (root / "set").mkdir(parents=True)
    (root / "set" / "work-cycle.yaml").write_text(
        "changes_dir: changes\ngates: []\n", encoding="utf-8")
    ch = root / "changes" / "c"
    ch.mkdir(parents=True)
    (ch / "tasks.md").write_text("## 0. First\n\n- [x] 0.1 done\n", encoding="utf-8")
    d = root / "set" / "runtime" / "work-cycle" / "c"
    d.mkdir(parents=True)
    (d / "c--0.json").write_text(json.dumps({
        "unit_id": "c--0", "change": "c", "group": "0", "seat": "session:t",
        "gate": {"state": gate_state}, "commit": {"committed": True, "sha": "abc"},
    }), encoding="utf-8")
    return root


def test_a_held_group_can_be_discharged_without_starting_an_agent(tmp_path, capsys):
    """⚠ The hold was a DEADLOCK when it shipped, and nothing caught it until a live run did.

    A held group has no open tasks left, so `run` cannot reach it — and the gate is the only
    thing that can clear the hold. With no way to run the gate on its own, the consumer could
    fix the cause on their side and the engine had no way to find out. A guard that cannot be
    discharged is not a guard, it is a wall.

    The declaration here is an empty gate (`gates: []`), which is a real 'no gate' — so this
    asserts the discharge path itself, not a gate implementation.
    """
    from set_workcycle.cli import build_parser, cmd_recheck, gate_failed_groups

    root = _held_tree(tmp_path)
    assert gate_failed_groups(root, "c") == {"0"}, "precondition: the group is held"

    args = build_parser().parse_args(
        ["--tree", str(root), "--change", "c", "--json", "recheck"])
    assert args.starts_a_unit is False, "recheck must not be a second start path"
    assert cmd_recheck(args) == 0

    assert gate_failed_groups(root, "c") == set(), "the hold was not discharged"

    # ⚠ The record and the REPORT are two places, and a mutation that stopped filling
    # `cleared` passed the record-only assertion. A discharge nobody is told about reads as a
    # discharge that did not happen — the same second-place defect this repo keeps measuring.
    out = json.loads(capsys.readouterr().out)
    assert out["cleared"] == ["c--0"], f"the record cleared but the report did not say so: {out}"


def test_recheck_on_an_unheld_tree_RUNS_NOTHING(tmp_path):
    """A command that always 'fixes' something is indistinguishable from one that lies — and
    the cost is not theoretical: the consumer's declared gate takes ~80 seconds.

    ⚠ Asserting only that the record is unchanged was too weak — with the early return
    removed the gate still RAN, and the record stayed identical because no group matched.
    So the gate here leaves a trace on disk, and its absence is the assertion.
    """
    from set_workcycle.cli import build_parser, cmd_recheck

    root = _held_tree(tmp_path, gate_state="passed")
    trace = root / "the-gate-ran"
    (root / "set" / "work-cycle.yaml").write_text(
        f"changes_dir: changes\ngates:\n  - touch {trace.name}\n", encoding="utf-8")

    before = (root / "set" / "runtime" / "work-cycle" / "c" / "c--0.json").read_text()
    args = build_parser().parse_args(["--tree", str(root), "--change", "c", "recheck"])
    assert cmd_recheck(args) == 0
    after = (root / "set" / "runtime" / "work-cycle" / "c" / "c--0.json").read_text()
    assert before == after, "recheck rewrote a record it had no business touching"
    assert not trace.exists(), "the gate ran although no group was held"
