"""A field's ROLE is declared by the project; the framework never infers it.

The load-bearing tests here are the negative ones. A renderer that recognised `pid` as an
identifier would pass every positive test in this file and would have moved one project's
vocabulary into a framework meant to serve the next one too.
"""

import json

import pytest

from set_orch.project_status import (
    PAIRED_ROLES,
    SIMPLE_ROLES,
    StatusResult,
    _display_roles,
    field_roles,
    parse_envelope,
)


def envelope(**extra):
    payload = {"contractVersion": 1, "command": "current", "ok": True, "data": {}}
    payload.update(extra)
    return json.dumps(payload)


# --- the declaration reaches the result ------------------------------------------------

def test_a_declared_role_is_carried_off_the_envelope():
    r = parse_envelope("current", envelope(display={"pid": "id"}))
    assert r.ok
    assert r.display == {"pid": "id"}


def test_the_result_docstring_names_display():
    """The enumeration is load-bearing: a caller who guesses a name gets the empty shape back.

    `getattr(result, "displays", {})` does not raise — it returns `{}`, which is
    indistinguishable from a project that declared nothing. So the list of field names in the
    docstring is a contract, and this keeps it in step.
    """
    assert "`display`" in StatusResult.__doc__


def test_an_answer_without_the_key_declares_nothing():
    r = parse_envelope("current", envelope())
    assert r.display == {}


# --- the vocabulary is closed ----------------------------------------------------------

@pytest.mark.parametrize("role", sorted(SIMPLE_ROLES))
def test_every_simple_role_in_the_vocabulary_survives_parsing(role):
    assert _display_roles({"f": role}) == {"f": role}


@pytest.mark.parametrize("form", sorted(PAIRED_ROLES))
def test_every_paired_role_in_the_vocabulary_survives_parsing(form):
    assert _display_roles({"f": {form: "other"}}) == {"f": {form: "other"}}


def test_an_unknown_role_is_dropped_silently_rather_than_refused():
    """The fail direction, and it is the point of the whole key.

    A refusal would mean a producer shipping a new role blanks a working surface — the framework
    dictating someone else's release order. Dropping means the value renders as it does today.
    """
    assert _display_roles({"size": "bytes", "pid": "id"}) == {"pid": "id"}


def test_a_style_request_is_not_a_role():
    """`display` is the key style leaks through. Each of these is one plausible request away."""
    assert _display_roles({"a": "bold", "b": "red", "c": "%.2f", "d": "right"}) == {}


def test_a_paired_role_without_a_partner_name_is_not_a_role():
    assert _display_roles({"a": {"progressOf": ""}, "b": {"progressOf": None}}) == {}
    assert _display_roles({"c": {"progressOf": "x", "limitOf": "y"}}) == {}


def test_a_malformed_declaration_costs_the_decoration_not_the_answer():
    r = parse_envelope("current", envelope(display=["pid"], data={"pid": 1}))
    assert r.ok, "a broken decoration must never turn a good measurement into a gap"
    assert r.display == {}
    assert r.data == {"pid": 1}


# --- resolving against the data --------------------------------------------------------

def test_a_declared_field_present_in_the_data_gets_its_role():
    assert field_roles({"pid": 3218705}, {"pid": "id"}) == {"pid": "id"}


def test_a_field_nested_at_any_depth_still_gets_its_role():
    data = {"running": {"debug": {"pid": 42}}}
    assert field_roles(data, {"pid": "id"}) == {"pid": "id"}


def test_a_field_inside_a_list_still_gets_its_role():
    data = {"runs": [{"other": 1}, {"pid": 7}]}
    assert field_roles(data, {"pid": "id"}) == {"pid": "id"}


def test_an_undeclared_field_named_pid_gets_NO_role():
    """The load-bearing negative. Make the framework recognise the name and this is what fails."""
    assert field_roles({"pid": 3218705, "elapsedSec": 1151}, {}) == {}
    assert field_roles({"pid": 3218705}, {"turns": "count"}) == {}


def test_a_declared_field_the_data_does_not_carry_produces_NOTHING():
    """Not a role, not a placeholder, and not a note that something is missing.

    A declaration is not data. A surface reporting on declared-but-absent fields announces an
    absence it never measured — the mirror of the false value this family of keys exists to stop.
    """
    assert field_roles({"running": None}, {"pid": "id", "log": "path"}) == {}


def test_a_dotted_declaration_matches_nothing():
    """The shape a producer reaches for first, whose failure is SILENT: no role, no error, and
    the declaration looks correct on their side."""
    assert field_roles({"running": {"pid": 4}}, {"running.pid": "id"}) == {}


# --- the paired rule -------------------------------------------------------------------

def test_a_pair_resolves_when_its_partner_is_a_sibling():
    data = {"tasksDone": 6, "tasksTotal": 7}
    assert field_roles(data, {"tasksDone": {"progressOf": "tasksTotal"}}) == {
        "tasksDone": {"progressOf": "tasksTotal"},
    }


def test_a_pair_whose_partner_is_absent_is_dropped():
    assert field_roles({"tasksDone": 6}, {"tasksDone": {"progressOf": "tasksTotal"}}) == {}


def test_a_partner_in_a_DIFFERENT_object_is_not_borrowed():
    """The dangerous direction: a bar built from another run's total is wrong AND plausible.

    This is the one place the any-depth rule is suspended, so it is the one place a later
    'simplification' to a single walk would look correct and silently produce a believable lie.
    """
    data = {"running": {"tasksDone": 6}, "lastFinished": {"tasksTotal": 99}}
    assert field_roles(data, {"tasksDone": {"progressOf": "tasksTotal"}}) == {}


def test_a_non_numeric_partner_is_not_a_partner():
    data = {"tasksDone": 6, "tasksTotal": "seven"}
    assert field_roles(data, {"tasksDone": {"progressOf": "tasksTotal"}}) == {}


def test_a_boolean_partner_is_not_a_number():
    """`isinstance(True, int)` is True in Python, so a bool passes a naive numeric check and a
    bar would be drawn out of `6 of True`."""
    data = {"tasksDone": 6, "tasksTotal": True}
    assert field_roles(data, {"tasksDone": {"progressOf": "tasksTotal"}}) == {}


def test_a_zero_partner_is_still_a_partner():
    """`0` is falsy and a truthiness check would drop it. A run with zero tasks is a real state
    and must render as such rather than silently losing its role."""
    data = {"tasksDone": 0, "tasksTotal": 0}
    assert field_roles(data, {"tasksDone": {"progressOf": "tasksTotal"}}) == {
        "tasksDone": {"progressOf": "tasksTotal"},
    }


def test_the_first_occurrence_wins_when_a_name_repeats():
    data = {"a": {"pid": 1}, "b": {"pid": 2}}
    assert field_roles(data, {"pid": "id"}) == {"pid": "id"}


def test_no_declaration_means_no_walk_and_no_roles():
    assert field_roles({"pid": 1}, {}) == {}


# --- the transport ---------------------------------------------------------------------

def test_the_snapshot_carries_display_to_the_api():
    from set_orch.project_status import StatusSnapshot

    snap = StatusSnapshot()
    snap.results["current"] = StatusResult(
        command="current", ok=True, data={"pid": 1}, display={"pid": "id"},
    )
    assert snap.to_dict()["commands"]["current"]["display"] == {"pid": "id"}
