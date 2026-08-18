"""Task-group resolution: groups, edges, selection, slice, carry-over, reading list.

Written with the change `work-cycle-engine-apply-first`, group 3. Every test here has been
run against a deliberately broken implementation and observed to FAIL — a test written
alongside a fix that also passes without it proves nothing and looks like proof forever.
The mutations used are named in each test's docstring, so the check can be repeated rather
than believed.
"""
from __future__ import annotations

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
