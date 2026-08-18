"""The deferred-work connector: conditions, stop markers, and the answer directory.

Written with the change `work-cycle-engine-apply-first`, group 5. Three of the behaviours
below exist because they were measured breaking in production elsewhere, and each test names
which one it guards — a test whose reason is forgotten is a test that gets relaxed.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_workcycle.connector import (  # noqa: E402
    ANSWERS_REL,
    MAX_PARSE_ATTEMPTS,
    QUARANTINE_REL,
    ConditionRequired,
    ResumeCondition,
    answer_filename,
    awaiting_tasks,
    clear_awaiting,
    intake,
    mark_awaiting,
    write_answer,
)


def _tasks(tmp_path: Path, body: str = None) -> Path:
    p = tmp_path / "tasks.md"
    p.write_text(textwrap.dedent(body or """
        ## 3. Group three

        <!-- depends: none -->

        - [ ] 3.1 alpha
        - [ ] 3.2 bravo
        - [x] 3.3 charlie
    """).lstrip("\n"), encoding="utf-8")
    return p


# ── 5.1 the resume condition ──────────────────────────────────────────────────────────────


def test_a_unit_cannot_be_set_aside_without_a_condition():
    """A condition that is not named cannot be observed, so nothing would ever release it."""
    with pytest.raises(ConditionRequired):
        ResumeCondition.require(None)


def test_a_human_decision_is_a_condition_and_identifies_the_decision():
    c = ResumeCondition.human_decision("Which auth provider?", task="3.2")
    assert c.awaits_a_person is True
    assert c.to_dict()["detail"] == "Which auth provider?"
    assert c.to_dict()["task"] == "3.2"


def test_an_external_dependency_is_expressible_by_the_same_mechanism():
    """The third prospective consumer stops on a system, not a person. Had the abstraction
    said 'awaiting human', a word would have excluded them."""
    c = ResumeCondition.external_system("the staging database")
    assert c.awaits_a_person is False
    assert c.dependency == "the staging database"
    assert "human" not in json.dumps(c.to_dict()).lower()


def test_a_decision_with_no_question_and_a_dependency_with_no_name_are_both_refused():
    with pytest.raises(ConditionRequired):
        ResumeCondition.human_decision("   ")
    with pytest.raises(ConditionRequired):
        ResumeCondition.external_system("")


# ── 5.2 the durable stop marker ───────────────────────────────────────────────────────────


def test_an_open_decision_is_written_into_the_task_file_with_its_question(tmp_path):
    tasks = _tasks(tmp_path)
    assert mark_awaiting(tasks, "3.2", "Which auth provider?") is True
    line = [l for l in tasks.read_text(encoding="utf-8").splitlines() if "3.2" in l][0]
    assert line.strip().startswith("- [?]")
    assert "Which auth provider?" in line


def test_the_marker_outlives_the_run_that_produced_it(tmp_path):
    """It is in the file, so any later reader — the engine restarted, or a person — sees it.
    A lock file would not survive this and would not be visible to the person."""
    tasks = _tasks(tmp_path)
    mark_awaiting(tasks, "3.2", "Which auth provider?")
    assert awaiting_tasks(tasks) == [("3.2", "Which auth provider?")]


def test_marking_touches_only_the_task_s_own_line(tmp_path):
    """Marking is the only mutation permitted on a project's task file; reformatting or
    rewriting it is out of scope."""
    tasks = _tasks(tmp_path)
    before = tasks.read_text(encoding="utf-8").splitlines()
    mark_awaiting(tasks, "3.2", "Q?")
    after = tasks.read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(changed) == 1 and "3.2" in after[changed[0]]


def test_an_answer_releases_the_task_back_to_open(tmp_path):
    tasks = _tasks(tmp_path)
    mark_awaiting(tasks, "3.2", "Q?")
    assert clear_awaiting(tasks, "3.2") is True
    line = [l for l in tasks.read_text(encoding="utf-8").splitlines() if "3.2" in l][0]
    assert line.strip().startswith("- [ ]") and "awaiting" not in line
    assert awaiting_tasks(tasks) == []


def test_marking_a_task_that_is_not_there_is_reported_not_guessed(tmp_path):
    assert mark_awaiting(_tasks(tmp_path), "9.9", "Q?") is False


# ── 5.3 the keyed directory ───────────────────────────────────────────────────────────────


def test_an_answer_carries_its_key_inside_the_document(tmp_path):
    path = write_answer(tmp_path, "c", "3.2", "use OIDC", source="dashboard")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["change"] == "c" and payload["task"] == "3.2"


def test_an_answer_for_a_task_that_is_not_awaiting_is_unmatched_and_left_in_place(tmp_path):
    """Discarding it would throw away a person's work because the engine's own state was
    momentarily behind."""
    path = write_answer(tmp_path, "c", "9.9", "an answer", source="chat")
    result = intake(tmp_path, awaiting={"c#3.2"})
    assert [a.key for a in result.unmatched] == ["c#9.9"]
    assert result.applied == []
    assert path.exists(), "the document is left where it was"


def test_an_answer_for_an_awaiting_task_is_applied(tmp_path):
    write_answer(tmp_path, "c", "3.2", "use OIDC", source="dashboard")
    result = intake(tmp_path, awaiting={"c#3.2"})
    assert [a.key for a in result.applied] == ["c#3.2"]
    assert result.applied[0].answer == "use OIDC"


# ── 5.4 a partially written document ──────────────────────────────────────────────────────


def test_a_half_written_document_is_deferred_not_quarantined_on_its_first_failure(tmp_path):
    """Quarantining on the first failure buries a human decision over a timing accident —
    six documents sat quarantined that way where this was measured."""
    directory = tmp_path / ANSWERS_REL
    directory.mkdir(parents=True)
    truncated = directory / "chat--20260818T100000.json"
    truncated.write_text('{"change": "c", "task": "3.2", "answ', encoding="utf-8")

    result = intake(tmp_path, awaiting={"c#3.2"})
    assert result.quarantined == []
    assert [n for n, _, _ in result.deferred] == [truncated.name]
    assert truncated.exists(), "still eligible for a later intake"


def test_a_deferred_document_that_later_parses_is_consumed_normally(tmp_path):
    directory = tmp_path / ANSWERS_REL
    directory.mkdir(parents=True)
    doc = directory / "chat--20260818T100000.json"
    doc.write_text('{"change": "c", "task": "3.2", "answ', encoding="utf-8")
    intake(tmp_path, awaiting={"c#3.2"})

    doc.write_text(json.dumps({"change": "c", "task": "3.2", "answer": "yes",
                               "source": "chat"}), encoding="utf-8")
    result = intake(tmp_path, awaiting={"c#3.2"})
    assert [a.key for a in result.applied] == ["c#3.2"]


def test_a_persistently_malformed_document_is_quarantined_with_its_reason(tmp_path):
    directory = tmp_path / ANSWERS_REL
    directory.mkdir(parents=True)
    doc = directory / "chat--20260818T100000.json"
    doc.write_text("not json at all", encoding="utf-8")

    for _ in range(MAX_PARSE_ATTEMPTS - 1):
        assert intake(tmp_path, awaiting={"c#3.2"}).quarantined == []
    result = intake(tmp_path, awaiting={"c#3.2"})

    assert [n for n, _ in result.quarantined] == [doc.name]
    assert not doc.exists()
    quarantined = tmp_path / QUARANTINE_REL / doc.name
    assert quarantined.exists()
    reason = (tmp_path / QUARANTINE_REL / (doc.name + ".reason.txt")).read_text(encoding="utf-8")
    assert "successive intakes" in reason


def test_the_connector_never_treats_its_own_bookkeeping_as_an_answer(tmp_path):
    """Found by a smoke test, and its direction is the bad one: the intake state file fails
    to parse as an answer, is deferred, and after three passes the connector quarantines its
    own memory of what it has already consumed — the measurement inside the corpus."""
    write_answer(tmp_path, "c", "3.2", "yes", source="chat")
    for _ in range(MAX_PARSE_ATTEMPTS + 1):
        result = intake(tmp_path, awaiting={"c#3.2"})
        assert result.quarantined == [], result.quarantined
        assert result.deferred == [], result.deferred
    assert (tmp_path / "set/runtime/work-cycle/answers/.intake.json").is_file()


# ── 5.5 several answers for one key ───────────────────────────────────────────────────────


def test_two_uploaders_answering_the_same_question_do_not_collide(tmp_path):
    a = write_answer(tmp_path, "c", "3.2", "from chat", source="chat", when="20260818T100000")
    b = write_answer(tmp_path, "c", "3.2", "from the dashboard", source="dashboard",
                     when="20260818T100000")
    assert a.name != b.name, "the same key at the same second still yields two files"
    assert "chat" in a.name and "dashboard" in b.name


def test_the_newest_answer_is_applied_and_the_others_are_retained(tmp_path):
    older = write_answer(tmp_path, "c", "3.2", "the first answer", source="chat",
                         when="20260818T090000")
    newer = write_answer(tmp_path, "c", "3.2", "the second answer", source="dashboard",
                         when="20260818T110000")
    result = intake(tmp_path, awaiting={"c#3.2"})
    assert [a.answer for a in result.applied] == ["the second answer"]
    assert [a.answer for a in result.superseded] == ["the first answer"]
    assert older.exists() and newer.exists(), "nothing is deleted"


def test_a_generated_name_carries_its_source_and_a_timestamp():
    name = answer_filename("dashboard", "20260818T101112")
    assert name.startswith("dashboard--") and "20260818T101112" in name


# ── 5.7 consumption is recorded ───────────────────────────────────────────────────────────


def test_consumption_is_stamped_on_the_answer_and_in_a_log(tmp_path):
    """Directory state lied in both directions where this was measured: consumed answers
    still present, unconsumed answers taken for processed."""
    path = write_answer(tmp_path, "c", "3.2", "yes", source="chat")
    intake(tmp_path, awaiting={"c#3.2"})

    assert "consumed_at" in json.loads(path.read_text(encoding="utf-8"))
    log = (tmp_path / "set/runtime/work-cycle/answers/.consumed.jsonl").read_text(encoding="utf-8")
    assert json.loads(log.splitlines()[0])["key"] == "c#3.2"


def test_consumed_and_unconsumed_are_distinguishable_without_counting_files(tmp_path):
    consumed = write_answer(tmp_path, "c", "3.2", "yes", source="chat", when="20260818T090000")
    intake(tmp_path, awaiting={"c#3.2"})
    pending = write_answer(tmp_path, "c", "3.1", "later", source="chat", when="20260818T100000")

    files_before = len(list((tmp_path / ANSWERS_REL).glob("*.json")))
    result = intake(tmp_path, awaiting={"c#3.1"})
    files_after = len(list((tmp_path / ANSWERS_REL).glob("*.json")))

    assert files_before == files_after, "the file count says nothing; it did not change"
    assert consumed.name in result.already_consumed
    assert [a.path.name for a in result.applied] == [pending.name]


def test_an_answer_is_not_applied_twice(tmp_path):
    write_answer(tmp_path, "c", "3.2", "yes", source="chat")
    assert len(intake(tmp_path, awaiting={"c#3.2"}).applied) == 1
    assert intake(tmp_path, awaiting={"c#3.2"}).applied == []
