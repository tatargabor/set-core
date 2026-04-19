"""Tests for Section 6 — lineage-scoped phase offset.

Covers:
  - 6.5 v1 archive 0,1,2 + replan 1,2 → shifted to 3,4
  - 6.6 v1 archive 0,1,2 + fresh start v2 with 1,2 → no offset, stays 1,2
  - 6.7 sentinel restart same lineage → picks up after archived max
  - 6.8 brand-new project (empty archive + state) → offset 0
  - AC-14a, AC-14b, AC-14c, AC-14d
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.planner import (
    _apply_phase_offset_to_plan,
    compute_phase_offset,
    enrich_plan_metadata,
)
from set_orch.state import init_state, load_state, save_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


def _setup(tmp_path, *, archived_phases_v1=(), live_phase=None, lineage="docs/spec.md"):
    """Project with state + archive seeded for a given lineage."""
    proj = tmp_path / "proj"
    proj.mkdir()
    plan_path = str(proj / "plan.json")
    state_path = str(proj / "state.json")
    plan = {
        "plan_version": 1,
        "brief_hash": "h",
        "plan_phase": "initial",
        "plan_method": "api",
        "input_path": lineage,
        "changes": [
            {"name": "alpha", "scope": "s", "complexity": "M",
             "phase": live_phase or 1},
        ],
    }
    with open(plan_path, "w") as fh:
        json.dump(plan, fh)
    init_state(plan_path, state_path,
               spec_path=lineage, project_path=str(proj))

    # Seed archive with v1 lineage entries.
    archive_path = os.path.join(os.path.dirname(state_path), "state-archive.jsonl")
    with open(archive_path, "w") as fh:
        for p in archived_phases_v1:
            fh.write(json.dumps({
                "name": f"v1-phase-{p}", "phase": p, "status": "merged",
                "spec_lineage_id": "docs/spec-v1.md",
            }) + "\n")
    return proj, state_path


# ---------------------------------------------------------------------------
# compute_phase_offset
# ---------------------------------------------------------------------------


def test_offset_zero_for_missing_state(tmp_path):
    """A truly empty project (no state, no archive) → offset 0."""
    proj = tmp_path / "proj"
    proj.mkdir()
    state_path = str(proj / "state.json")
    assert compute_phase_offset(state_path, "docs/spec.md") == 0


def test_offset_for_lineage_with_only_live_change_at_phase_one(tmp_path):
    """With only the initial live change at phase 1, offset = 1."""
    proj, state_path = _setup(tmp_path, lineage="docs/spec.md")
    assert compute_phase_offset(state_path, "docs/spec.md") == 1


def test_offset_returns_max_for_lineage(tmp_path):
    proj, state_path = _setup(tmp_path,
                              archived_phases_v1=[0, 1, 2],
                              lineage="docs/spec-v1.md",
                              live_phase=None)
    # archive max = 2 plus live alpha @ phase 1 → max = 2 → offset = 2.
    # _apply uses shift = offset - min_new_phase + 1; for min=1 this
    # becomes shift=2 → new phase 1 maps to 3, satisfying AC-14a.
    assert compute_phase_offset(state_path, "docs/spec-v1.md") == 2


def test_offset_ignores_other_lineages(tmp_path):
    """v1 has phases 0,1,2; v2 query should see no v1 contribution."""
    proj, state_path = _setup(tmp_path,
                              archived_phases_v1=[0, 1, 2],
                              lineage="docs/spec-v1.md")
    assert compute_phase_offset(state_path, "docs/spec-v2.md") == 0


def test_offset_lineage_none_returns_zero(tmp_path):
    proj, state_path = _setup(tmp_path,
                              archived_phases_v1=[0, 1, 2],
                              lineage="docs/spec-v1.md")
    assert compute_phase_offset(state_path, None) == 0


def test_offset_includes_live_state_phases(tmp_path):
    """Live state's lineage-tagged changes contribute to the max as well."""
    proj, state_path = _setup(tmp_path, lineage="docs/spec-v1.md")
    state = load_state(state_path)
    state.changes[0].phase = 5
    save_state(state, state_path)
    assert compute_phase_offset(state_path, "docs/spec-v1.md") == 5


# ---------------------------------------------------------------------------
# _apply_phase_offset_to_plan
# ---------------------------------------------------------------------------


def test_apply_offset_shifts_phases():
    plan = {"changes": [
        {"name": "a", "phase": 1},
        {"name": "b", "phase": 2},
    ]}
    _apply_phase_offset_to_plan(plan, offset=3)
    # offset 3, min new phase 1 → shift = 3 - 1 + 1 = 3 → [4, 5]
    assert [c["phase"] for c in plan["changes"]] == [4, 5]


def test_apply_offset_zero_keeps_phases():
    plan = {"changes": [{"name": "a", "phase": 1}, {"name": "b", "phase": 2}]}
    _apply_phase_offset_to_plan(plan, offset=0)
    assert [c["phase"] for c in plan["changes"]] == [1, 2]


def test_apply_offset_clamps_to_one():
    plan = {"changes": [{"name": "a", "phase": -3}]}
    _apply_phase_offset_to_plan(plan, offset=2)
    # min_new_phase auto-derived = -3.  shift = 2 - (-3) + 1 = 6 → -3 + 6 = 3
    assert plan["changes"][0]["phase"] == 3


def test_apply_offset_respects_min_new_phase_param():
    plan = {"changes": [{"name": "a", "phase": 5}]}
    _apply_phase_offset_to_plan(plan, offset=10, min_new_phase=5)
    # shift = 10 - 5 + 1 = 6, 5 + 6 = 11
    assert plan["changes"][0]["phase"] == 11


def test_replan_continues_lineage_numbering_via_apply():
    """Direct shift check matching AC-14a math."""
    plan = {"changes": [{"name": "a", "phase": 1}, {"name": "b", "phase": 2}]}
    # Lineage max = 2 → offset = 2.  shift = 2 - 1 + 1 = 2 → [3, 4].
    _apply_phase_offset_to_plan(plan, offset=2)
    assert [c["phase"] for c in plan["changes"]] == [3, 4]


# ---------------------------------------------------------------------------
# AC-14a: v1 archive 0,1,2 + replan 1,2 → 3,4
# ---------------------------------------------------------------------------


def test_replan_continues_lineage_numbering(tmp_path):
    proj, state_path = _setup(tmp_path,
                              archived_phases_v1=[0, 1, 2],
                              lineage="docs/spec-v1.md")
    plan = {"changes": [
        {"name": "page-a", "phase": 1},
        {"name": "page-b", "phase": 2},
    ]}
    enriched = enrich_plan_metadata(
        plan, hash_val="h", input_mode="spec",
        input_path="docs/spec-v1.md", plan_version=2,
        replan_cycle=1, state_path=state_path,
    )
    phases = [c["phase"] for c in enriched["changes"]]
    assert phases == [3, 4]


# ---------------------------------------------------------------------------
# AC-14c / 6.6: v1 archive present, fresh state on v2 spec → no offset
# ---------------------------------------------------------------------------


def test_other_lineage_phases_are_ignored_fresh_v2_start(tmp_path):
    """v1 has phases 0,1,2 archived under spec-v1.md; sentinel starts fresh
    on spec-v2.md (no live v2 state yet) → v2's plan keeps phases 1,2."""
    proj = tmp_path / "proj"
    proj.mkdir()
    state_path = str(proj / "state.json")

    # No v2 state — fresh sentinel start.  Only the v1 archive exists.
    archive_path = os.path.join(os.path.dirname(state_path), "state-archive.jsonl")
    with open(archive_path, "w") as fh:
        for p in (0, 1, 2):
            fh.write(json.dumps({"name": f"v1-{p}", "phase": p, "status": "merged",
                                 "spec_lineage_id": "docs/spec-v1.md"}) + "\n")
    # Fabricate a state.json that already records spec_lineage_id = v2 but
    # has zero v2 changes (the planner's first run).
    with open(state_path, "w") as fh:
        json.dump({
            "plan_version": 1, "brief_hash": "h", "plan_phase": "initial",
            "plan_method": "api", "status": "running",
            "created_at": "2026-01-01T00:00:00",
            "spec_lineage_id": "docs/spec-v2.md",
            "sentinel_session_id": "abc",
            "changes": [],
        }, fh)

    new_plan = {"changes": [
        {"name": "v2-page-a", "phase": 1},
        {"name": "v2-page-b", "phase": 2},
    ]}
    enriched = enrich_plan_metadata(
        new_plan, hash_val="h", input_mode="spec",
        input_path="docs/spec-v2.md", plan_version=2,
        replan_cycle=1, state_path=state_path,
    )
    # v1 archive entries are ignored (different lineage); no v2 changes
    # contribute → offset 0 → no shift.
    assert [c["phase"] for c in enriched["changes"]] == [1, 2]


# ---------------------------------------------------------------------------
# AC-14d / 6.8: brand-new project → offset 0
# ---------------------------------------------------------------------------


def test_brand_new_project_no_offset(tmp_path):
    """Brand-new project = empty archive + empty live state (no changes).
    First plan-write in this state must keep planner-native numbering."""
    proj = tmp_path / "proj"
    proj.mkdir()
    state_path = str(proj / "state.json")
    # Empty state with no changes — emulates the moment before init_state
    # has been called (or after init_state with an empty plan).
    with open(state_path, "w") as fh:
        json.dump({
            "plan_version": 1, "brief_hash": "h", "plan_phase": "initial",
            "plan_method": "api", "status": "running",
            "created_at": "2026-01-01T00:00:00",
            "spec_lineage_id": "docs/spec.md",
            "sentinel_session_id": "abc",
            "changes": [],
        }, fh)

    new_plan = {"changes": [
        {"name": "a", "phase": 1},
        {"name": "b", "phase": 2},
    ]}
    enriched = enrich_plan_metadata(
        new_plan, hash_val="h", input_mode="spec",
        input_path="docs/spec.md", plan_version=2,
        replan_cycle=1, state_path=state_path,
    )
    assert [c["phase"] for c in enriched["changes"]] == [1, 2]


# ---------------------------------------------------------------------------
# AC-14b / 6.7: sentinel restart same lineage continues numbering
# ---------------------------------------------------------------------------


def test_restart_same_spec_continues_after_archive(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    state_path = str(proj / "state.json")
    plan_path = str(proj / "plan.json")
    plan = {
        "plan_version": 1, "brief_hash": "h", "plan_phase": "initial",
        "plan_method": "api", "input_path": "docs/spec-v1.md",
        "changes": [{"name": "current", "scope": "s", "complexity": "M", "phase": 5}],
    }
    with open(plan_path, "w") as fh:
        json.dump(plan, fh)
    init_state(plan_path, state_path,
               spec_path="docs/spec-v1.md", project_path=str(proj))
    # Archive contains v1 phases 1,2,3,4 (lineage matches).
    archive_path = os.path.join(os.path.dirname(state_path), "state-archive.jsonl")
    with open(archive_path, "w") as fh:
        for p in (1, 2, 3, 4):
            fh.write(json.dumps({"name": f"v1-{p}", "phase": p, "status": "merged",
                                 "spec_lineage_id": "docs/spec-v1.md"}) + "\n")

    # max(live=5, archive=4) = 5 → offset = 5.  New plan with phases 1,2 →
    # shift = 5 - 1 + 1 = 5; new phases 6, 7.
    new_plan = {"changes": [
        {"name": "next-a", "phase": 1},
        {"name": "next-b", "phase": 2},
    ]}
    enriched = enrich_plan_metadata(
        new_plan, hash_val="h", input_mode="spec",
        input_path="docs/spec-v1.md", plan_version=2,
        replan_cycle=1, state_path=state_path,
    )
    assert [c["phase"] for c in enriched["changes"]] == [6, 7]
