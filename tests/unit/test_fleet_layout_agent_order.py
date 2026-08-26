"""One project's hand-made agent order — what is stored, and what it must not touch.

Two properties decide whether this store is worth having, and both are about
things that go wrong silently:

**It keeps keys whose agent is not running.** That is the whole reason the order
is stored rather than derived. An entry pruned because its agent is stopped comes
back at the end of the strip, and the reader's arrangement rewrites itself with
nothing to notice.

**It does not move the arrangement's version.** That version is the optimistic
lock protecting hand-made project groups. If dragging a tab bumped it, the
reader's own next group edit would 409 — a conflict manufactured by the conflict
machinery.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.fleet import layout as fleet_layout


@pytest.fixture
def doc(tmp_path):
    return str(tmp_path / "fleet-layout.json")


def test_the_order_round_trips_verbatim(doc):
    stored = fleet_layout.save_agent_order(["b", "a", "c"], project="proj", path=doc)
    assert stored == ["b", "a", "c"]
    assert fleet_layout.load(doc)["agent_order"] == {"proj": ["b", "a", "c"]}


def test_a_key_whose_agent_is_not_running_is_kept(doc):
    """The store never asks what a key names, so it cannot prune one."""
    fleet_layout.save_agent_order(["gone", "here"], project="proj", path=doc)
    served = fleet_layout.apply_to(fleet_layout.load(doc), ["proj"])
    assert served["agent_order"]["proj"] == ["gone", "here"]


def test_the_order_is_per_project(doc):
    fleet_layout.save_agent_order(["a", "b"], project="one", path=doc)
    fleet_layout.save_agent_order(["z"], project="two", path=doc)
    assert fleet_layout.load(doc)["agent_order"] == {"one": ["a", "b"], "two": ["z"]}


def test_writing_one_project_leaves_the_others_alone(doc):
    fleet_layout.save_agent_order(["a", "b"], project="one", path=doc)
    fleet_layout.save_agent_order(["z"], project="two", path=doc)
    fleet_layout.save_agent_order(["b", "a"], project="one", path=doc)
    assert fleet_layout.load(doc)["agent_order"]["two"] == ["z"]


def test_the_arrangement_version_does_not_move(doc):
    """The lock protecting hand-made groups is not this store's to spend."""
    fleet_layout.save({"groups": [], "parked": [], "ungrouped": []}, path=doc)
    before = fleet_layout.load(doc)["version"]
    fleet_layout.save_agent_order(["a"], project="proj", path=doc)
    assert fleet_layout.load(doc)["version"] == before


def test_an_empty_order_removes_the_key(doc):
    """"No order" and "an order of nothing" must not be two states."""
    fleet_layout.save_agent_order(["a"], project="proj", path=doc)
    assert fleet_layout.save_agent_order([], project="proj", path=doc) == []
    assert "proj" not in fleet_layout.load(doc)["agent_order"]


def test_duplicates_are_dropped(doc):
    assert fleet_layout.save_agent_order(["a", "a", "b"], project="p", path=doc) == ["a", "b"]


def test_a_write_with_no_project_is_refused(doc):
    with pytest.raises(ValueError):
        fleet_layout.save_agent_order(["a"], project="  ", path=doc)


def test_the_arrangement_survives_an_order_write(doc):
    """The two stores share a file; one must not clear the other."""
    fleet_layout.save({"groups": [{"name": "SET", "projects": ["proj"]}],
                       "parked": [], "ungrouped": []}, path=doc)
    fleet_layout.save_agent_order(["a"], project="proj", path=doc)
    served = fleet_layout.apply_to(fleet_layout.load(doc), ["proj"])
    assert [g["name"] for g in served["groups"]] == ["SET"]
    assert served["agent_order"] == {"proj": ["a"]}


def test_the_route_refuses_a_body_with_no_project(monkeypatch, tmp_path):
    """The API's half of the same refusal — the shape docking regressed into once."""
    from fastapi.testclient import TestClient
    from set_orch.server import create_app
    from set_orch.fleet import layout as layout_module

    monkeypatch.setattr(layout_module, "default_layout_path",
                        lambda: str(tmp_path / "fleet-layout.json"))
    client = TestClient(create_app(web_dist_dir=None))

    refused = client.put("/api/fleet/layout/agent-order", json={"project": "  ", "order": ["a"]})
    assert refused.status_code == 400
    assert "project" in refused.json()["detail"]

    stored = client.put("/api/fleet/layout/agent-order", json={"project": "p", "order": ["b", "a"]})
    assert stored.status_code == 200
    assert stored.json() == {"project": "p", "order": ["b", "a"]}

    served = client.get("/api/fleet/layout")
    assert served.json()["agent_order"] == {"p": ["b", "a"]}


def test_a_rename_carries_the_agents_place(doc):
    """Without this the agent keeps its old key and drops to the end of the strip."""
    fleet_layout.save_agent_order(["a", "b", "c"], project="p", path=doc)
    assert fleet_layout.relabel_agent_order("b", "b2", path=doc) == 1
    assert fleet_layout.load(doc)["agent_order"]["p"] == ["a", "b2", "c"]


def test_a_rename_onto_a_key_the_list_already_has_leaves_one_entry(doc):
    fleet_layout.save_agent_order(["a", "b"], project="p", path=doc)
    fleet_layout.relabel_agent_order("a", "b", path=doc)
    assert fleet_layout.load(doc)["agent_order"]["p"] == ["b"]


def test_renaming_an_agent_with_no_stored_place_changes_nothing(doc):
    fleet_layout.save_agent_order(["a"], project="p", path=doc)
    assert fleet_layout.relabel_agent_order("zzz", "yyy", path=doc) == 0
    assert fleet_layout.load(doc)["agent_order"]["p"] == ["a"]
