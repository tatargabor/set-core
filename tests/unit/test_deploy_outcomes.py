"""The deploy engine's per-file result, as DATA — task 2.0 of `module-install-writer`.

The engine has always reported what it did as human prose. A second caller now needs the
same facts structurally, to build a report for a screen, and the tempting shortcut is to
parse the sentences back into structure. That would be a parser over human-facing text,
which is a defect class this repository has already paid for more than once.

So the outcome is produced first and the sentence is rendered from it. Two things have to
hold for that to be safe, and both are asserted here:

1. **The prose is unchanged.** `set-project init` prints it, and this refactor sits on that
   command's critical path. Proven once against the previous commit in an isolated
   worktree — `PYTHONPATH=/tmp/prosebase/lib`, import origin asserted, `FileOutcome`
   absent there and present here — over four force/dry_run combinations, byte-identical.
   That proof cannot live in a test, so what lives here is the golden text it produced.
2. **The two forms cannot drift.** Every outcome carries the message that was printed for
   it, and the printed list is exactly those messages in order. A helper that appended to
   only one of the two would be a second place for them to disagree, and the disagreement
   would be invisible in whichever form the reader is not looking at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from set_orch.profile_deploy import FileOutcome, _deploy_single_template


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """One template exercising every branch the loop has, and a project that has already
    lived a little: a scaffold file it rewrote, a protected rule it edited, a merge target
    with an extra key, and an instruction file to be announced in."""
    tpl, tgt = tmp_path / "tpl", tmp_path / "proj"
    (tpl / "rules").mkdir(parents=True)
    (tgt / "set").mkdir(parents=True)
    (tpl / "a.md").write_text("A\n")
    (tpl / "b.yaml").write_text("k: 1\n")
    (tpl / "c.md").write_text("C\n")
    (tpl / "rules" / "r.md").write_text("R\n")
    (tpl / "manifest.yaml").write_text(
        "version: '1.0.0'\n"
        "core:\n"
        "  - path: a.md\n    replace: true\n"
        "  - path: b.yaml\n    merge: true\n"
        "  - path: c.md\n    once: true\n"
        "  - path: rules/r.md\n    protected: true\n"
        "announce:\n  body: hello\n  file: CLAUDE.md\n"
    )
    (tgt / "c.md").write_text("the project's own C\n")
    (tgt / ".claude" / "rules").mkdir(parents=True)
    (tgt / ".claude" / "rules" / "r.md").write_text("edited by the project\n")
    (tgt / "CLAUDE.md").write_text("# project\n")
    (tgt / "b.yaml").write_text("k: 1\nz: 9\n")
    return tpl, tgt


GOLDEN = {
    (False, False): [
        "  Deployed: a.md",
        "  Skipped (exists): b.yaml",
        "  Skipped (exists): c.md",
        "  Skipped (exists): .claude/rules/r.md",
        "  Announced tpl in CLAUDE.md",
    ],
    (False, True): [
        "  Would deploy: a.md",
        "  Skipped (exists): b.yaml",
        "  Skipped (exists): c.md",
        "  Skipped (exists): .claude/rules/r.md",
        "  Would announce tpl in CLAUDE.md",
    ],
    (True, False): [
        "  Deployed: a.md",
        "  Merged (no new keys): b.yaml",
        "  Skipped (scaffold, already present): c.md",
        "  Skipped (protected): .claude/rules/r.md",
        "  Announced tpl in CLAUDE.md",
    ],
    (True, True): [
        "  Would deploy: a.md",
        "  Would merge: b.yaml",
        "  Would skip (scaffold, already present): c.md",
        "  Skipped (protected): .claude/rules/r.md",
        "  Would announce tpl in CLAUDE.md",
    ],
}


@pytest.mark.parametrize("force,dry_run", sorted(GOLDEN))
def test_the_prose_this_command_prints_is_unchanged(tmp_path, force, dry_run):
    """The golden text, so a later tidy-up of the messages fails HERE rather than in
    somebody's terminal.

    Two of these lines are inconsistent on purpose and are pinned as they are: `exists`
    and `protected` say "Skipped" even in a dry run, where every other skip says "Would
    skip". Fixing that is a change to what `set-project init` prints, and it does not
    belong in a change about something else.
    """
    tpl, tgt = _fixture(tmp_path)
    assert _deploy_single_template(tpl, tgt, force=force, dry_run=dry_run) == GOLDEN[(force, dry_run)]


@pytest.mark.parametrize("force,dry_run", sorted(GOLDEN))
def test_the_outcomes_and_the_messages_cannot_drift_apart(tmp_path, force, dry_run):
    """The invariant that makes the golden test above worth having.

    Without it, a later branch could append a message and forget the outcome — and the
    structured caller would silently lose a file while the printed output stayed right.
    That failure is invisible from either side alone.
    """
    tpl, tgt = _fixture(tmp_path)
    outcomes: list[FileOutcome] = []
    messages = _deploy_single_template(tpl, tgt, force=force, dry_run=dry_run,
                                       outcomes=outcomes)
    assert [o.message for o in outcomes] == messages


def test_every_branch_of_the_loop_reports_an_action_and_a_path(tmp_path):
    """A `skipped` with no reason is the silent skip this whole design forbids, wearing
    a report's clothes."""
    tpl, tgt = _fixture(tmp_path)
    outcomes: list[FileOutcome] = []
    _deploy_single_template(tpl, tgt, force=True, outcomes=outcomes)

    by_path = {o.path: o for o in outcomes if o.action != "announced"}
    assert set(by_path) == {"a.md", "b.yaml", "c.md", ".claude/rules/r.md"}
    assert by_path["a.md"].action == "deployed"
    assert by_path["b.yaml"].action == "merged"
    assert by_path["c.md"].action == "skipped"
    assert by_path[".claude/rules/r.md"].action == "skipped"
    for outcome in outcomes:
        if outcome.action == "skipped":
            assert outcome.reason, f"{outcome.path} was skipped without saying why"


def test_the_announcement_is_an_outcome_too(tmp_path):
    """It edits a file the PROJECT owns. Left out of the outcomes it would be the one
    write no report mentions — and a write nobody reports is the same class of defect as
    a skip nobody reports.
    """
    tpl, tgt = _fixture(tmp_path)
    outcomes: list[FileOutcome] = []
    _deploy_single_template(tpl, tgt, force=True, outcomes=outcomes)
    announced = [o for o in outcomes if o.action == "announced"]
    assert announced and announced[0].path == "CLAUDE.md"


def test_the_sink_is_optional_and_two_runs_do_not_share_one(tmp_path):
    """The sink is optional — every existing caller passes nothing — and it must not have
    a mutable default.

    The second half is what this test is really for. `outcomes: List[FileOutcome] = []`
    reads as harmless and passes any check that only asks whether the prose still comes
    back; what it does is give every call that passes nothing the SAME list, which then
    grows for the life of the process. The failure is invisible to the caller that
    triggered it and lands on some later reader.

    An earlier version of this test asserted only that the prose still arrives, and the
    mutation to a mutable default was NOT caught. Kept as two runs and an identity check,
    because that is the shape the bug actually has.
    """
    tpl, tgt = _fixture(tmp_path)
    first = _deploy_single_template(tpl, tgt, force=True)
    assert first[0] == "  Deployed: a.md"

    import inspect
    default = inspect.signature(_deploy_single_template).parameters["outcomes"].default
    assert default is None, (
        f"`outcomes` has a mutable default ({default!r}); every call that passes nothing "
        "would share one list"
    )

    tpl2, tgt2 = _fixture(tmp_path / "second")
    mine: list[FileOutcome] = []
    _deploy_single_template(tpl2, tgt2, force=True, outcomes=mine)
    assert len(mine) == len(first), (
        "a caller's own sink came back holding another run's outcomes"
    )
