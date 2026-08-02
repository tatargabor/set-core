"""The gate: a path is followable only because the project's LIVE answer says so.

Every case here is built as real files in a temporary tree rather than mocked, because two of the
refusals — a symlink leaving the tree, and `..` segments resolving out of it — exist precisely
because a *string* check passes them. A mock that returns the string would agree with the code
under test about the one thing the code is supposed to doubt.
"""

import json
import os
import stat

import pytest

from set_orch import status_follow
from set_orch.project_status import StatusConfig


def make_project(tmp_path, data, follow=None, ok=True):
    """A project whose contract command prints one envelope. No mocks: a real script, run."""
    payload = {"contractVersion": 1, "command": "current", "ok": ok, "data": data}
    if follow is not None:
        payload["follow"] = follow
    script = tmp_path / "answer.py"
    script.write_text(
        "import sys\n"
        f"print({json.dumps(json.dumps(payload))})\n",
        encoding="utf-8",
    )
    cfg = StatusConfig(command=["python3", str(script)], cwd=str(tmp_path), source="test")
    return cfg


def test_a_declared_path_is_accepted(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "run.jsonl").write_text("x\n", encoding="utf-8")
    cfg = make_project(tmp_path, {"running": {"log": "logs/run.jsonl"}}, follow=["log"])

    d = status_follow.decide(tmp_path, "current", "logs/run.jsonl", config=cfg)

    assert d.ok, d.error
    assert d.field == "log"
    assert d.path == (tmp_path / "logs" / "run.jsonl").resolve()


def test_an_undeclared_but_readable_file_in_the_tree_is_refused(tmp_path):
    """The cheap rule would have allowed this, and it is the reason the gate is not the cheap rule."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "run.jsonl").write_text("x\n", encoding="utf-8")
    secret = tmp_path / ".env"
    secret.write_text("TOKEN=abc\n", encoding="utf-8")
    cfg = make_project(tmp_path, {"running": {"log": "logs/run.jsonl"}}, follow=["log"])

    d = status_follow.decide(tmp_path, "current", ".env", config=cfg)

    assert not d.ok
    assert d.error_class == "not-followable"
    assert d.path is None


def test_a_path_the_answer_no_longer_names_is_refused(tmp_path):
    """Followable a minute ago is not followable now — the check is against the live answer."""
    (tmp_path / "old.jsonl").write_text("x\n", encoding="utf-8")
    cfg = make_project(tmp_path, {"running": None}, follow=["log"])

    d = status_follow.decide(tmp_path, "current", "old.jsonl", config=cfg)

    assert not d.ok
    assert d.error_class == "no-declaration"


def test_a_symlink_pointing_outside_the_tree_is_refused(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("not yours\n", encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    link = project / "escape.log"
    os.symlink(outside, link)
    cfg = make_project(project, {"running": {"log": "escape.log"}}, follow=["log"])

    d = status_follow.decide(project, "current", "escape.log", config=cfg)

    assert not d.ok, "a symlink out of the tree must be refused even when the project declares it"
    assert d.error_class == "outside-project"


def test_a_string_only_check_would_have_passed_the_symlink(tmp_path):
    """Held as a test so a later 'simplification' to string comparison fails instead of looking equal.

    The declared value and the requested value are identical strings, both plainly relative and
    free of `..`. Everything a string check can see says this is inside the tree.
    """
    outside = tmp_path.parent / "outside-secret-2.txt"
    outside.write_text("not yours\n", encoding="utf-8")
    project = tmp_path / "proj2"
    project.mkdir()
    os.symlink(outside, project / "escape.log")

    requested = "escape.log"
    assert not requested.startswith("/") and ".." not in requested
    assert status_follow._resolved_under(project, requested) is None


def test_traversal_segments_cannot_escape_the_root(tmp_path):
    project = tmp_path / "proj3"
    project.mkdir()
    (tmp_path / "sibling.txt").write_text("no\n", encoding="utf-8")
    cfg = make_project(project, {"running": {"log": "a.jsonl"}}, follow=["log"])

    d = status_follow.decide(project, "current", "../sibling.txt", config=cfg)

    assert not d.ok
    assert d.error_class == "outside-project"


def test_traversal_that_lands_back_inside_is_not_a_way_past_the_declaration(tmp_path):
    """`logs/../logs/run.jsonl` IS the declared file, so it is accepted — resolved on both sides."""
    project = tmp_path / "proj4"
    (project / "logs").mkdir(parents=True)
    (project / "logs" / "run.jsonl").write_text("x\n", encoding="utf-8")
    cfg = make_project(project, {"running": {"log": "logs/run.jsonl"}}, follow=["log"])

    d = status_follow.decide(project, "current", "logs/../logs/run.jsonl", config=cfg)

    assert d.ok, d.error


def test_an_absolute_path_outside_the_tree_is_refused(tmp_path):
    project = tmp_path / "proj5"
    project.mkdir()
    cfg = make_project(project, {"running": {"log": "a.jsonl"}}, follow=["log"])

    d = status_follow.decide(project, "current", "/etc/passwd", config=cfg)

    assert not d.ok
    assert d.error_class == "outside-project"


def test_the_project_root_itself_is_not_followable(tmp_path):
    project = tmp_path / "proj6"
    project.mkdir()
    cfg = make_project(project, {"running": {"log": "a.jsonl"}}, follow=["log"])

    d = status_follow.decide(project, "current", ".", config=cfg)

    assert not d.ok
    assert d.error_class == "outside-project"


def test_a_project_declaring_nothing_offers_nothing(tmp_path):
    project = tmp_path / "proj7"
    project.mkdir()
    (project / "run.jsonl").write_text("x\n", encoding="utf-8")
    cfg = make_project(project, {"running": {"log": "run.jsonl"}})  # no `follow`

    d = status_follow.decide(project, "current", "run.jsonl", config=cfg)

    assert not d.ok
    assert d.error_class == "no-declaration"


def test_a_failing_command_refuses_rather_than_defaulting_open(tmp_path):
    """The direction that matters: an unanswerable project must not become a permissive one."""
    project = tmp_path / "proj8"
    project.mkdir()
    (project / "run.jsonl").write_text("x\n", encoding="utf-8")
    cfg = make_project(project, {"running": {"log": "run.jsonl"}}, follow=["log"], ok=False)

    d = status_follow.decide(project, "current", "run.jsonl", config=cfg)

    assert not d.ok
    assert d.error_class == "command-failed"


def test_a_command_name_from_a_url_never_reaches_a_process(tmp_path):
    project = tmp_path / "proj9"
    project.mkdir()
    cfg = make_project(project, {"running": {"log": "a.jsonl"}}, follow=["log"])

    d = status_follow.decide(project, "current; rm -rf /", "a.jsonl", config=cfg)

    assert not d.ok
    assert d.error_class == "bad-command"


def test_an_empty_request_is_refused_without_asking_the_project(tmp_path):
    project = tmp_path / "proj10"
    project.mkdir()
    cfg = make_project(project, {"running": {"log": "a.jsonl"}}, follow=["log"])

    for empty in ("", "   ", None):
        d = status_follow.decide(project, "current", empty, config=cfg)
        assert not d.ok
        assert d.error_class == "not-followable"


def test_every_refusal_names_a_documented_error_class(tmp_path):
    """The contract requires set-core to name its own failures; an undocumented name is a gap."""
    project = tmp_path / "proj11"
    project.mkdir()
    cfg = make_project(project, {"running": {"log": "a.jsonl"}}, follow=["log"])

    seen = set()
    for path in ("", "/etc/passwd", "nope.jsonl"):
        d = status_follow.decide(project, "current", path, config=cfg)
        if not d.ok:
            seen.add(d.error_class)
    for bad in ("current; rm", ):
        seen.add(status_follow.decide(project, bad, "a", config=cfg).error_class)

    assert seen <= set(status_follow.ERROR_CLASSES), seen - set(status_follow.ERROR_CLASSES)


def test_a_field_nested_one_level_deeper_is_still_accepted(tmp_path):
    """A producer asked whether they may move the field under a `debug` object. They may.

    Recorded as a test rather than as an answer on a channel, because they are moving their own
    output on the strength of it: if this selector ever narrowed to the top level, their follow
    control would vanish SILENTLY, and a vanished control is indistinguishable from "nothing is
    running". The answer has to be something that breaks a build, not something someone remembers.
    """
    project = tmp_path / "nested"
    (project / "logs").mkdir(parents=True)
    (project / "logs" / "run.jsonl").write_text("x\n", encoding="utf-8")
    cfg = make_project(
        project,
        {"running": {"state": "running", "debug": {"pid": 42, "log": "logs/run.jsonl"}}},
        follow=["log"],
    )

    d = status_follow.decide(project, "current", "logs/run.jsonl", config=cfg)

    assert d.ok, d.error
    assert d.field == "log"
