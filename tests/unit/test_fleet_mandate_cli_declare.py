"""`set-fleet-mandate declare` against the declare ROUTE's own model.

The command and the route were written and tested apart, and the first time the command was
run against the route every declaration was refused: it sent `kind` and a nested `scope`,
and the route forbids unknown fields. So the body is checked here against the model the
route validates with — a rename on either side fails this file.
"""

from __future__ import annotations

import argparse

import pytest

from set_orch.api.fleet_mandate import DeclareBody
from set_orch.fleet import mandate_cli


def _args(**over):
    base = dict(goal="ship the importer", label=None, session=None, done_when=None, path=None, change=None)
    base.update(over)
    return argparse.Namespace(**base)


@pytest.mark.parametrize("over", [
    dict(label="proj-1200"),
    dict(session="sess-1"),
    dict(label="proj-1200", done_when="tests pass", path=["src/a/", "src/b/"], change="importer"),
])
def test_the_body_is_one_the_route_accepts(over):
    body = mandate_cli.declare_body(_args(**over), environ={})
    parsed = DeclareBody(**body)          # raises on any field the route does not take
    assert parsed.goal == "ship the importer"
    assert parsed.paths == (over.get("path") or [])
    assert parsed.change == over.get("change") and parsed.done_when == over.get("done_when")
    assert (parsed.label, parsed.session_id) == (over.get("label"), over.get("session"))


def test_the_body_carries_no_field_the_route_forbids():
    body = mandate_cli.declare_body(_args(label="a", path=["src/"]), environ={})
    assert set(body) <= set(DeclareBody.model_fields)
    assert "kind" not in body and "scope" not in body


def test_with_nobody_named_the_session_of_the_caller_is_used():
    body = mandate_cli.declare_body(_args(), environ={"CLAUDE_CODE_SESSION_ID": "own-session"})
    assert body["session_id"] == "own-session" and "label" not in body
    assert mandate_cli.declare_body(_args(), environ={}) is None


def test_the_parser_and_the_body_agree_on_every_option():
    parsed = mandate_cli.build_parser().parse_args(
        ["declare", "ship it", "--label", "a", "--done-when", "green", "--path", "x/", "--path", "y/", "--change", "c"])
    body = mandate_cli.declare_body(parsed, environ={})
    assert body == {"goal": "ship it", "label": "a", "done_when": "green", "paths": ["x/", "y/"], "change": "c"}
    DeclareBody(**body)
