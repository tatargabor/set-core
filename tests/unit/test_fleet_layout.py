"""The fleet screen's arrangement — groups, order, parked (D-2, 2026-08-19).

What is asserted here is the boundary between ARRANGEMENT and INVENTORY, because
every hazard in this module is a way for one to be mistaken for the other. The
arrangement says where the user wants things; discovery says what exists. A file
that answered both would make a project vanish from the screen by being absent
from a list somebody wrote by hand weeks ago.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from set_orch.fleet import layout as layout_mod
from set_orch.fleet.layout import LayoutConflict, apply_to, load, normalise, save


def _path(tmp_path):
    return str(tmp_path / "fleet-layout.json")


# --------------------------------------------------------------------------- #
# arrangement is not inventory
# --------------------------------------------------------------------------- #

def test_a_project_nobody_arranged_still_appears():
    """The false-absence class, in its most ordinary form: register a new project
    and it is in no group, so a screen that renders only the arrangement would
    not show it at all — and an empty place looks exactly like nothing to show.
    """
    arranged = normalise({"groups": [{"name": "set", "projects": ["set-core"]}]})
    joined = apply_to(arranged, ["set-core", "brand-new"])
    assert joined["ungrouped"] == ["brand-new"]
    assert joined["groups"][0]["projects"] == ["set-core"]


def test_a_project_that_vanished_is_REPORTED_not_silently_dropped():
    """The mirror image. A name disappearing from a hand-made arrangement is
    information — the user put it there deliberately — so it comes back as
    `missing` rather than as an arrangement that appears to have edited itself.
    """
    arranged = normalise({"groups": [{"name": "set", "projects": ["set-core", "deleted-thing"]}],
                          "parked": ["also-gone"]})
    joined = apply_to(arranged, ["set-core"])
    assert joined["groups"][0]["projects"] == ["set-core"]
    assert joined["groups"][0]["missing"] == ["deleted-thing"]
    assert sorted(joined["missing"]) == ["also-gone", "deleted-thing"]
    assert joined["parked"] == []


def test_the_order_within_a_group_is_the_users_not_the_registrys():
    """The whole reason manual ordering was chosen: related projects sit next to
    each other. Re-sorting them would undo the decision on every render.
    """
    arranged = normalise({"groups": [{"name": "mine", "projects": ["zeta", "alpha", "mid"]}]})
    joined = apply_to(arranged, ["alpha", "mid", "zeta"])
    assert joined["groups"][0]["projects"] == ["zeta", "alpha", "mid"]


def test_a_project_can_only_be_in_one_place():
    """Two homes would render it twice and make its position depend on iteration
    order — an arrangement that changes without anyone moving anything.
    """
    arranged = normalise({
        "groups": [{"name": "a", "projects": ["x", "y"]}, {"name": "b", "projects": ["x"]}],
        "parked": ["y", "z"],
    })
    assert arranged["groups"][0]["projects"] == ["x", "y"]
    assert arranged["groups"][1]["projects"] == []
    assert arranged["parked"] == ["z"]


def test_a_group_without_a_name_is_dropped_rather_than_rendered_blank():
    assert normalise({"groups": [{"projects": ["x"]}, {"name": "  ", "projects": ["y"]}]})["groups"] == []


# --------------------------------------------------------------------------- #
# persistence
# --------------------------------------------------------------------------- #

def test_a_missing_file_is_an_unarranged_screen_not_an_error(tmp_path):
    """A missing arrangement and an empty one mean the same thing, and both must
    produce a screen.
    """
    assert load(_path(tmp_path)) == {
        "version": 0, "groups": [], "parked": [], "ungrouped_order": [], "splits": {},
        "docks": {}, "docks_legacy": [],
    }


def test_an_unreadable_file_fails_toward_unarranged(tmp_path):
    path = _path(tmp_path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{ this is not json")
    assert load(path)["groups"] == []


def test_a_save_survives_a_round_trip(tmp_path):
    path = _path(tmp_path)
    saved = save({"groups": [{"name": "set", "projects": ["set-core"]}], "parked": ["old"]}, path=path)
    assert saved["version"] == 1
    again = load(path)
    assert again["groups"][0]["projects"] == ["set-core"]
    assert again["parked"] == ["old"]
    assert again["version"] == 1


def test_a_stale_write_is_refused_rather_than_silently_winning(tmp_path):
    """Two dashboard tabs are ordinary. The loser of a last-write-wins race would
    find an arrangement they never made, with no event to explain it and no way
    back — so a stale write is refused and the client can resolve it.
    """
    path = _path(tmp_path)
    save({"groups": [{"name": "a", "projects": ["x"]}]}, path=path)            # version 1
    save({"groups": [{"name": "b", "projects": ["x"]}]}, path=path, base_version=1)  # version 2

    with pytest.raises(LayoutConflict) as excinfo:
        save({"groups": [{"name": "c", "projects": ["x"]}]}, path=path, base_version=1)
    assert "reload before saving" in str(excinfo.value)
    assert load(path)["groups"][0]["name"] == "b", "the refused write must not have landed"


def test_the_write_is_atomic_and_leaves_no_partial_file(tmp_path):
    """Written through a temp file and renamed. Never `open(p, "w")` in the same
    expression that reads `p` — that truncates before the read, and an empty file
    is a valid "nothing arranged" shape, so every downstream check stays green on
    the damage.
    """
    path = _path(tmp_path)
    save({"groups": [{"name": "a", "projects": ["x"]}]}, path=path)
    leftovers = [f for f in os.listdir(tmp_path) if f.startswith(".fleet-layout.")]
    assert leftovers == []
    with open(path, encoding="utf-8") as handle:
        assert json.load(handle)["groups"][0]["name"] == "a"


def test_the_store_lives_in_the_frameworks_durable_per_user_root(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert layout_mod.default_layout_path() == str(tmp_path / "set-core" / "fleet-layout.json")


# --------------------------------------------------------------------------- #
# what the client must not have to INFER — added 2026-08-19 from UI feedback
# --------------------------------------------------------------------------- #

def test_a_group_carries_its_stored_order_so_a_save_cannot_lose_a_missing_member():
    """`GET` splits a group into present and missing; `PUT` replaces the whole
    document. A client rebuilding the list by concatenating the two loses each
    missing member's POSITION — it can only re-append — so an absent project
    drifts to the end of its group every time anything is saved. `order` is the
    stored list verbatim, so there is nothing to rebuild.
    """
    arranged = normalise({"groups": [{"name": "g", "projects": ["a", "GONE", "b"]}]})
    joined = apply_to(arranged, ["a", "b"])
    group = joined["groups"][0]
    assert group["projects"] == ["a", "b"]
    assert group["missing"] == ["GONE"]
    assert group["order"] == ["a", "GONE", "b"], "the position of the missing member is lost"


def test_parked_missing_is_stated_rather_than_left_to_subtraction():
    """The client used to derive this by removing every group's missing from the
    total. An inference standing in for data is where a wrong answer looks like
    a computed one.
    """
    arranged = normalise({"groups": [{"name": "g", "projects": ["a", "G1"]}],
                          "parked": ["b", "G2"]})
    joined = apply_to(arranged, ["a", "b"])
    assert joined["parked_missing"] == ["G2"]
    assert joined["parked_order"] == ["b", "G2"]
    assert sorted(joined["missing"]) == ["G1", "G2"]


def test_the_unassigned_block_keeps_the_order_the_user_gave_it():
    """Without this the unassigned block is the one part of a hand-arranged
    screen that cannot be arranged — a hole in the decision rather than a
    detail, since manual ordering is the whole of D-2.
    """
    arranged = normalise({"ungrouped_order": ["zeta", "alpha"]})
    joined = apply_to(arranged, ["alpha", "mid", "zeta"])
    assert joined["ungrouped"] == ["zeta", "alpha", "mid"], "ordered first, then the rest"


def test_an_ordered_name_that_joins_a_group_stops_being_unassigned():
    """One project, one place — the preference must not resurrect it."""
    arranged = normalise({"groups": [{"name": "g", "projects": ["zeta"]}],
                          "ungrouped_order": ["zeta", "alpha"]})
    assert arranged["ungrouped_order"] == ["alpha"]
    joined = apply_to(arranged, ["alpha", "zeta"])
    assert joined["ungrouped"] == ["alpha"]
    assert joined["groups"][0]["projects"] == ["zeta"]


# --------------------------------------------------------------------------- #
# draggable dividers — a position is not the arrangement, and an absent one is
# not a zero
# --------------------------------------------------------------------------- #

def test_a_divider_position_survives_a_round_trip(tmp_path):
    p = _path(tmp_path)
    layout_mod.save_splits({"projects": 320}, path=p)
    assert load(p)["splits"] == {"projects": 320}


def test_a_divider_nobody_dragged_is_absent_rather_than_zero(tmp_path):
    """The false-absence class, and its expensive direction.

    A pane stored at 0 renders as no pane at all, and nobody thinks to drag an
    edge they cannot see. So an unusable value is DROPPED — which restores the
    client's default — rather than coerced into a position the user never chose.
    """
    p = _path(tmp_path)
    layout_mod.save_splits({"projects": None, "dock": "wide", "empty": ""}, path=p)
    assert load(p)["splits"] == {}


def test_a_position_outside_the_recoverable_range_is_clamped_not_stored(tmp_path):
    """Zero and ten-thousand are both unrecoverable: one hides the pane, the
    other pushes its edge past the window. The server clamps to what can be
    grabbed again; the client clamps to what actually fits."""
    p = _path(tmp_path)
    layout_mod.save_splits({"a": 0, "b": 99999}, path=p)
    assert load(p)["splits"] == {"a": layout_mod.MIN_SPLIT, "b": layout_mod.MAX_SPLIT}


def test_storing_a_divider_does_not_bump_the_arrangements_version(tmp_path):
    """Otherwise dragging an edge invalidates the base version the project
    column is holding, and the user's next group edit 409s against their own
    dragging — a conflict manufactured entirely by the conflict machinery."""
    p = _path(tmp_path)
    saved = save({"groups": [{"name": "core", "projects": ["a"]}]}, path=p)
    before = saved["version"]
    layout_mod.save_splits({"projects": 300}, path=p)
    assert load(p)["version"] == before
    # And the arrangement itself is still there, not replaced by a splits-only doc.
    assert [g["name"] for g in load(p)["groups"]] == ["core"]


def test_saving_the_arrangement_does_not_wipe_dividers_it_never_mentioned(tmp_path):
    """The project column posts groups and says nothing about dividers. Saying
    nothing must not mean "delete these" — `normalise` returns `{}` for both, so
    without the preserve step the user's dragged edges vanish on every drag of a
    project."""
    p = _path(tmp_path)
    layout_mod.save_splits({"projects": 300}, path=p)
    save({"groups": [{"name": "core", "projects": ["a"]}]}, path=p)
    assert load(p)["splits"] == {"projects": 300}


def test_a_caller_that_explicitly_sends_no_dividers_clears_them(tmp_path):
    """The other half of the rule above: omission preserves, an explicit empty
    map clears. If both meant "preserve" there would be no way to reset."""
    p = _path(tmp_path)
    layout_mod.save_splits({"projects": 300}, path=p)
    save({"groups": [], "splits": {}}, path=p)
    assert load(p)["splits"] == {}


def test_apply_to_passes_dividers_through_unjoined():
    """A divider belongs to the screen, not to a project, so there is nothing
    for it to be missing FROM — it must not travel through the inventory join."""
    joined = apply_to(normalise({"splits": {"projects": 300}}), ["a"])
    assert joined["splits"] == {"projects": 300}


# --------------------------------------------------------------------------- #
# docked views — ONE PROJECT's arrangement, keyed by project since 2026-08-20
# --------------------------------------------------------------------------- #

def test_a_docked_view_survives_a_round_trip(tmp_path):
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "changes", "id": "v1", "edge": "right"}], project="p1", path=p)
    assert load(p)["docks"].get("p1", []) == [{"kind": "changes", "id": "v1", "edge": "right"}]


def test_an_unknown_edge_undocks_rather_than_defaulting_to_one(tmp_path):
    """Placing a view on an edge nobody chose is the false-value class: it
    renders, it looks deliberate, and it is wrong. Dropping the entry leaves the
    view undocked, which is a state the user can drag out of."""
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "changes", "id": "v1", "edge": "diagonal"}], project="p1", path=p)
    assert load(p)["docks"].get("p1", []) == []


def test_two_views_can_share_one_edge_and_keep_their_order(tmp_path):
    """A list rather than a map keyed by edge. A map would either forbid the
    second view or lose the order the user arranged them in."""
    p = _path(tmp_path)
    layout_mod.save_docks([
        {"kind": "changes", "id": "a", "edge": "right"},
        {"kind": "changes", "id": "b", "edge": "right"},
    ], project="p1", path=p)
    assert [d["id"] for d in load(p)["docks"].get("p1", [])] == ["a", "b"]


def test_one_instance_docks_in_one_place(tmp_path):
    p = _path(tmp_path)
    layout_mod.save_docks([
        {"kind": "changes", "id": "a", "edge": "right"},
        {"kind": "changes", "id": "a", "edge": "left"},
    ], project="p1", path=p)
    assert load(p)["docks"].get("p1", []) == [{"kind": "changes", "id": "a", "edge": "right"}]


def test_docking_does_not_bump_the_arrangements_version(tmp_path):
    p = _path(tmp_path)
    saved = save({"groups": [{"name": "core", "projects": ["a"]}]}, path=p)
    layout_mod.save_docks([{"kind": "changes", "id": "v1", "edge": "top"}], project="p1", path=p)
    assert load(p)["version"] == saved["version"]
    assert [g["name"] for g in load(p)["groups"]] == ["core"]


def test_saving_the_arrangement_does_not_wipe_docking_it_never_mentioned(tmp_path):
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "changes", "id": "v1", "edge": "bottom"}], project="p1", path=p)
    save({"groups": []}, path=p)
    assert len(load(p)["docks"].get("p1", [])) == 1


def test_an_explicit_empty_dock_list_clears(tmp_path):
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "changes", "id": "v1", "edge": "bottom"}], project="p1", path=p)
    save({"groups": [], "docks": {}}, path=p)
    assert load(p)["docks"].get("p1", []) == []


def test_docking_and_its_size_are_stored_by_DIFFERENT_mechanisms_on_purpose(tmp_path):
    """A docked view's size is a divider position, and goes through `splits`.
    Two stores for one edge is how a screen renders a width nobody set — so the
    dock entry carries no size at all, and this asserts that it stays that way."""
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "changes", "id": "v1", "edge": "right", "size": 400}], project="p1", path=p)
    assert load(p)["docks"].get("p1", []) == [{"kind": "changes", "id": "v1", "edge": "right"}]


def test_an_entry_missing_its_identity_is_dropped(tmp_path):
    p = _path(tmp_path)
    layout_mod.save_docks([
        {"kind": "", "id": "v1", "edge": "right"},
        {"kind": "changes", "id": "", "edge": "right"},
        "not-a-dock",
        {"kind": "changes", "id": "ok", "edge": "right"},
    ], project="p1", path=p)
    assert [d["id"] for d in load(p)["docks"].get("p1", [])] == ["ok"]


def test_a_collapsed_band_stays_collapsed(tmp_path):
    """Collapsed is part of the arrangement, not a browser-local mood: a reader
    who tidies a band away means it to stay tidied."""
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "agent", "id": "a", "edge": "right", "collapsed": True}], project="p1", path=p)
    assert load(p)["docks"].get("p1", []) == [{"kind": "agent", "id": "a", "edge": "right", "collapsed": True}]


def test_an_uncollapsed_band_carries_no_flag_at_all(tmp_path):
    """Written only when true. An absent flag is the ordinary case, and a key on
    every entry saying `false` is noise that later reads as a decision."""
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "agent", "id": "a", "edge": "right", "collapsed": False}], project="p1", path=p)
    assert load(p)["docks"].get("p1", []) == [{"kind": "agent", "id": "a", "edge": "right"}]


# --------------------------------------------------------------------------- #
# docking is PER PROJECT — corrected by the user 2026-08-20
# --------------------------------------------------------------------------- #

def test_docking_in_one_project_leaves_another_projects_docking_alone(tmp_path):
    """The defect this shape exists to prevent, stated as an assertion.

    Docking was screen-wide, so a terminal docked while looking at one project
    held the same edge in every other project — where nothing could render in
    it, and the band could only say *"no running agent with this terminal in
    <the other project>"*. The reader lost the panel to an empty band naming a
    project they were not looking at.
    """
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "agent", "id": "a-1", "edge": "right"}], project="alpha", path=p)
    layout_mod.save_docks([{"kind": "agent", "id": "b-1", "edge": "bottom"}], project="beta", path=p)
    stored = load(p)["docks"]
    assert [d["id"] for d in stored["alpha"]] == ["a-1"]
    assert [d["id"] for d in stored["beta"]] == ["b-1"]


def test_undocking_everything_in_one_project_removes_only_that_key(tmp_path):
    """"Nothing docked" and "never docked here" render the same, so the key goes
    rather than being stored as an empty list that grows the document forever."""
    p = _path(tmp_path)
    layout_mod.save_docks([{"kind": "agent", "id": "a-1", "edge": "right"}], project="alpha", path=p)
    layout_mod.save_docks([{"kind": "agent", "id": "b-1", "edge": "bottom"}], project="beta", path=p)
    layout_mod.save_docks([], project="alpha", path=p)
    stored = load(p)["docks"]
    assert "alpha" not in stored
    assert [d["id"] for d in stored["beta"]] == ["b-1"]


def test_a_write_without_a_project_is_refused_rather_than_stored_screen_wide(tmp_path):
    """The missing argument IS the old defect. A default would let the shape
    regress by a caller forgetting one, silently and only for whoever docked."""
    p = _path(tmp_path)
    with pytest.raises(ValueError):
        layout_mod.save_docks([{"kind": "agent", "id": "a-1", "edge": "right"}], project="  ", path=p)


def test_a_document_written_before_per_project_docking_keeps_its_list(tmp_path):
    """A deleted entry and one that was never written are indistinguishable, so
    the flat list survives — under its own key, rendered by nobody. It is NOT
    adopted into a project: the document does not say which project each entry
    belonged to, and guessing is what produced the defect."""
    p = _path(tmp_path)
    with open(p, "w", encoding="utf-8") as handle:
        json.dump({"version": 3, "groups": [],
                   "docks": [{"kind": "agent", "id": "old-1", "edge": "right"}]}, handle)
    stored = load(p)
    assert stored["docks"] == {}
    assert stored["docks_legacy"] == [{"kind": "agent", "id": "old-1", "edge": "right"}]


def test_the_legacy_list_survives_a_later_write(tmp_path):
    p = _path(tmp_path)
    with open(p, "w", encoding="utf-8") as handle:
        json.dump({"version": 3, "groups": [],
                   "docks": [{"kind": "agent", "id": "old-1", "edge": "right"}]}, handle)
    layout_mod.save_docks([{"kind": "agent", "id": "a-1", "edge": "right"}], project="alpha", path=p)
    save({"groups": [{"name": "core", "projects": ["alpha"]}]}, path=p)
    assert load(p)["docks_legacy"] == [{"kind": "agent", "id": "old-1", "edge": "right"}]
    assert [d["id"] for d in load(p)["docks"]["alpha"]] == ["a-1"]


def test_the_join_hands_the_client_a_map_it_can_pick_its_own_project_out_of(tmp_path):
    joined = apply_to(normalise({"docks": {"alpha": [{"kind": "agent", "id": "a-1", "edge": "right"}]}}), ["alpha"])
    assert joined["docks"] == {"alpha": [{"kind": "agent", "id": "a-1", "edge": "right"}]}
    assert joined["docks_legacy"] == []


# --------------------------------------------------------------------------- #
# relabel_dock — a dock names an agent, and an agent's name can change
# --------------------------------------------------------------------------- #

def _laid_out(tmp_path, *, docks, splits) -> str:
    p = str(tmp_path / "fleet-layout.json")
    pathlib.Path(p).write_text(json.dumps({
        "version": 5, "groups": [], "parked": [], "ungrouped_order": [],
        "splits": splits, "docks": docks, "docks_legacy": [],
    }))
    return p


def test_a_dock_and_its_width_both_follow_the_new_name(tmp_path):
    p = _laid_out(
        tmp_path,
        docks={"proj": [{"kind": "agent", "id": "old", "edge": "right"}]},
        splits={"dock:agent:old": 520, "projects": 300},
    )
    assert layout_mod.relabel_dock("agent", "old", "new", path=p) == {"docked": 1, "splits": 1}
    stored = json.loads(pathlib.Path(p).read_text())
    assert stored["docks"]["proj"] == [{"kind": "agent", "id": "new", "edge": "right"}]
    assert stored["splits"] == {"dock:agent:new": 520, "projects": 300}
    assert stored["version"] == 6


def test_a_dock_with_no_stored_width_is_carried_and_is_not_a_failure(tmp_path):
    """The ordinary case: nobody dragged the divider. A zero here must read as
    "there was no width", never as "the move failed".
    """
    p = _laid_out(tmp_path, docks={"proj": [{"kind": "agent", "id": "old", "edge": "left"}]}, splits={})
    assert layout_mod.relabel_dock("agent", "old", "new", path=p) == {"docked": 1, "splits": 0}
    assert json.loads(pathlib.Path(p).read_text())["docks"]["proj"][0]["id"] == "new"


def test_a_name_nothing_is_docked_to_writes_nothing_at_all(tmp_path):
    """Most renames touch no dock. Bumping the version for them would make every
    open screen believe the arrangement changed under it.
    """
    p = _laid_out(tmp_path, docks={"proj": [{"kind": "agent", "id": "other", "edge": "right"}]}, splits={})
    before = pathlib.Path(p).read_text()
    assert layout_mod.relabel_dock("agent", "old", "new", path=p) == {"docked": 0, "splits": 0}
    assert pathlib.Path(p).read_text() == before


def test_a_dock_of_another_kind_with_the_same_id_is_left_alone(tmp_path):
    """`id` is only unique within a kind — a panel called `old` that is not an
    agent is a different thing that happens to share a name.
    """
    p = _laid_out(
        tmp_path,
        docks={"proj": [{"kind": "agent", "id": "old", "edge": "right"},
                        {"kind": "changes", "id": "old", "edge": "bottom"}]},
        splits={"dock:changes:old": 200},
    )
    assert layout_mod.relabel_dock("agent", "old", "new", path=p) == {"docked": 1, "splits": 0}
    stored = json.loads(pathlib.Path(p).read_text())
    assert [e["id"] for e in stored["docks"]["proj"]] == ["new", "old"]
    assert stored["splits"] == {"dock:changes:old": 200}


def test_the_legacy_dock_list_survives_a_relabel(tmp_path):
    """It is preserved and never rendered. A write that dropped it would delete
    the only evidence that those docks were ever made.
    """
    p = str(tmp_path / "fleet-layout.json")
    pathlib.Path(p).write_text(json.dumps({
        "version": 1, "groups": [], "parked": [], "ungrouped_order": [], "splits": {},
        "docks": {"proj": [{"kind": "agent", "id": "old", "edge": "right"}]},
        "docks_legacy": [{"kind": "agent", "id": "from-before", "edge": "right"}],
    }))
    layout_mod.relabel_dock("agent", "old", "new", path=p)
    assert json.loads(pathlib.Path(p).read_text())["docks_legacy"] == [
        {"kind": "agent", "id": "from-before", "edge": "right"}
    ]
