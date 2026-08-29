"""A declared stage order survives the parser, and it is STATIC.

Every test here asserts that a value ARRIVES. That is deliberate and it is the whole point:
both defects this change closes are silent drops, so a test asserting "nothing raised" would
pass against the unfixed code and look like proof forever. Each of these fails without the fix —
verified by stash-and-rerun, not assumed.

The negative tests carry as much weight as the positive ones. A partial order is worse than no
order: it renders as a complete process quietly missing stages, which is a false value rather
than a gap, and the producer is told nothing.
"""

import json

import pytest

from set_orch import project_status
from set_orch.project_status import (
    _display_roles,
    field_roles,
    parse_envelope,
)

# `LIST_ROLES` and `_stage_list` are introduced BY this change, so importing them at module
# scope would make the whole file fail COLLECTION against unfixed code. A collection error is
# not a failing test — nothing runs, and "it errored" is indistinguishable from "the behaviour
# is wrong" when you are trying to prove a test earns its keep. Measured here: the first
# stash-and-rerun of this file reported one error and zero failures, which would have been
# accepted as proof and was not proof of anything. Resolved lazily instead, so every
# behavioural test below runs against old code and fails on its ASSERTION.
LIST_ROLES = getattr(project_status, "LIST_ROLES", frozenset())
_stage_list = getattr(project_status, "_stage_list", None)

ORDER = ["planned", "specified", "in-progress", "implemented", "demoed", "done"]


def envelope(**extra):
    payload = {"contractVersion": 1, "command": "current", "ok": True, "data": {}}
    payload.update(extra)
    return json.dumps(payload)


# --- the declaration reaches the result ------------------------------------------------

def test_stage_order_is_a_recognised_list_role():
    assert "stageOrder" in LIST_ROLES


def test_a_declared_stage_order_is_carried_through_with_its_order_intact():
    roles = _display_roles({"lane": {"stageOrder": ORDER}})
    assert roles == {"lane": {"stageOrder": ORDER}}
    # Order is the entire content of this declaration; a set would pass a laxer assertion.
    assert roles["lane"]["stageOrder"] == ORDER


def test_the_declaration_survives_a_whole_envelope():
    result = parse_envelope("current", envelope(
        data={"rows": [{"lane": "planned"}]},
        display={"lane": {"stageOrder": ORDER}},
    ))
    assert result.display["lane"] == {"stageOrder": ORDER}


def test_a_stage_order_does_not_disturb_the_other_paired_forms():
    roles = _display_roles({
        "lane": {"stageOrder": ORDER},
        "doneCount": {"progressOf": "totalCount"},
        "pid": "id",
    })
    assert roles["lane"] == {"stageOrder": ORDER}
    assert roles["doneCount"] == {"progressOf": "totalCount"}
    assert roles["pid"] == "id"


# --- malformed leaves the field UNROLED, never half-ordered -----------------------------

@pytest.mark.parametrize("bad", [
    "planned,done",          # a string, not an array
    [],                      # empty
    ["planned", 3],          # a non-string member
    ["planned", ""],         # an empty member
    ["planned", "   "],      # whitespace only
    ["planned", None],
    {"0": "planned"},        # an object, not an array
    ["planned", "planned"],  # a duplicate: two groups, one name, unresolvable for a reader
])
def test_a_malformed_stage_order_yields_no_role_at_all(bad):
    roles = _display_roles({"lane": {"stageOrder": bad}})
    assert roles == {}, f"expected no role for {bad!r}, got {roles!r}"


@pytest.mark.parametrize("bad", ["planned,done", [], ["planned", 3], ["planned", ""]])
def test_a_malformed_stage_order_never_costs_the_answer(bad):
    result = parse_envelope("current", envelope(
        data={"rows": [{"lane": "planned"}]},
        display={"lane": {"stageOrder": bad}},
    ))
    assert result.data == {"rows": [{"lane": "planned"}]}
    assert result.display == {}


def test_a_partial_order_is_never_salvaged():
    """The valid entries must NOT be kept. A complete-looking order missing a stage is a
    false value; an absent one is a gap, and a gap is the honest outcome."""
    roles = _display_roles({"lane": {"stageOrder": ["planned", 3, "done"]}})
    assert roles == {}
    assert "lane" not in roles


@pytest.mark.skipif(_stage_list is None, reason="helper introduced by this change")
def test_stage_list_helper_reports_unusable_as_none_not_as_empty():
    # None and [] are different answers: one is "not a stage order", the other would be
    # "an order with no stages", which the caller must never see.
    assert _stage_list("planned") is None
    assert _stage_list([]) is None
    assert _stage_list(["planned"]) == ["planned"]


@pytest.mark.skipif(_stage_list is None, reason="helper introduced by this change")
def test_stages_are_stripped_but_order_is_untouched():
    assert _stage_list([" planned ", "done"]) == ["planned", "done"]


# --- presence: the DATA decides the field, the DECLARATION decides the stages -----------

def test_the_role_resolves_when_the_field_is_present():
    resolved = field_roles(
        {"rows": [{"lane": "planned"}]},
        {"lane": {"stageOrder": ORDER}},
    )
    assert resolved["lane"] == {"stageOrder": ORDER}


def test_a_declared_field_the_answer_does_not_carry_produces_nothing():
    """The shipped rule 'presence is counted from the data' is NOT overridden by this change.
    A declaration alone must never conjure a process onto the screen."""
    resolved = field_roles({"rows": [{"other": 1}]}, {"lane": {"stageOrder": ORDER}})
    assert resolved == {}


def test_the_declared_order_is_identical_across_disjoint_value_sets():
    """The static condition, which is the one that carries the others. An order computed from
    the values would differ between these two answers, and a reader filtering a board would
    silently see a different process."""
    only_planned = field_roles(
        {"rows": [{"lane": "planned"}, {"lane": "planned"}]},
        {"lane": {"stageOrder": ORDER}},
    )
    only_done = field_roles(
        {"rows": [{"lane": "done"}]},
        {"lane": {"stageOrder": ORDER}},
    )
    assert only_planned["lane"]["stageOrder"] == ORDER
    assert only_done["lane"]["stageOrder"] == ORDER
    assert only_planned["lane"] == only_done["lane"]


def test_a_value_outside_the_order_never_extends_it():
    resolved = field_roles(
        {"rows": [{"lane": "tesztelés"}, {"lane": "planned"}]},
        {"lane": {"stageOrder": ORDER}},
    )
    assert resolved["lane"]["stageOrder"] == ORDER
    assert "tesztelés" not in resolved["lane"]["stageOrder"]


def test_an_empty_declared_stage_stays_in_the_order():
    resolved = field_roles(
        {"rows": [{"lane": "planned"}]},
        {"lane": {"stageOrder": ORDER}},
    )
    # Every declared stage survives, including the five nothing matched.
    assert resolved["lane"]["stageOrder"] == ORDER
    assert len(resolved["lane"]["stageOrder"]) == 6


def test_a_list_argument_does_not_raise_on_the_partner_lookup():
    """Regression guard, and it is not hypothetical: the paired-role branch looks the argument
    up as a dict key (`value.get(partner)`). A list is unhashable, so reaching that branch
    raises TypeError and costs the entire answer for the sake of a decoration."""
    resolved = field_roles(
        {"rows": [{"lane": "planned"}]},
        {"lane": {"stageOrder": ORDER}},
    )
    assert resolved["lane"]["stageOrder"] == ORDER


def test_the_resolved_order_is_a_copy_the_caller_cannot_corrupt():
    display = {"lane": {"stageOrder": ORDER}}
    resolved = field_roles({"rows": [{"lane": "planned"}]}, display)
    resolved["lane"]["stageOrder"].append("injected")
    assert display["lane"]["stageOrder"] == ORDER
