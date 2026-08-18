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
    assert load(_path(tmp_path)) == {"version": 0, "groups": [], "parked": [], "ungrouped_order": []}


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
