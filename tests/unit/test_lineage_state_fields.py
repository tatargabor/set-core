"""Tests for Section 7 — spec_lineage_id and sentinel_session_id state fields.

Covers tasks 7.5–7.8:
  - sentinel start with --spec docs/spec-v1.md → state.spec_lineage_id matches
  - absolute and relative spec paths canonicalise to the same id
  - session_id survives replan; lineage survives replan and restart-same-spec
  - session_id is fresh after stop+start; lineage stays for same spec
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.state import (
    Change,
    OrchestratorState,
    init_state,
    load_state,
    save_state,
)
from set_orch.engine import _append_changes_to_state, _archive_completed_to_jsonl


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_plan(plan_path: str, *, input_path=None, changes=None) -> None:
    plan = {
        "plan_version": 1,
        "brief_hash": "h",
        "plan_phase": "initial",
        "plan_method": "api",
        "changes": changes or [
            {"name": "foundation", "scope": "s", "complexity": "M", "phase": 1},
            {"name": "catalog", "scope": "s", "complexity": "M", "phase": 2,
             "depends_on": ["foundation"]},
        ],
    }
    if input_path is not None:
        plan["input_path"] = input_path
    with open(plan_path, "w") as fh:
        json.dump(plan, fh)


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


# ---------------------------------------------------------------------------
# 7.5 — sentinel start with --spec docs/spec-v1.md
# ---------------------------------------------------------------------------


def test_init_state_with_spec_path_sets_lineage_id(project):
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path)
    init_state(plan_path, state_path,
               spec_path="docs/spec-v1.md",
               project_path=str(project))

    state = load_state(state_path)
    assert state.spec_lineage_id == "docs/spec-v1.md"
    assert state.sentinel_session_id is not None
    assert len(state.sentinel_session_id) == 32  # uuid hex
    assert state.sentinel_session_started_at is not None


def test_every_change_inherits_lineage_and_session(project):
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path)
    init_state(plan_path, state_path,
               spec_path="docs/spec-v1.md",
               project_path=str(project))

    state = load_state(state_path)
    for c in state.changes:
        assert c.spec_lineage_id == "docs/spec-v1.md"
        assert c.sentinel_session_id == state.sentinel_session_id
        assert c.sentinel_session_started_at == state.sentinel_session_started_at


def test_init_state_falls_back_to_plan_input_path(project):
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path, input_path="docs/spec-fallback.md")
    init_state(plan_path, state_path, project_path=str(project))

    state = load_state(state_path)
    assert state.spec_lineage_id == "docs/spec-fallback.md"


def test_init_state_without_spec_or_input_path_is_none(project, caplog):
    import logging
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path)  # no input_path
    with caplog.at_level(logging.WARNING, logger="set_orch.state"):
        init_state(plan_path, state_path, project_path=str(project))
    state = load_state(state_path)
    assert state.spec_lineage_id is None
    assert any("input_path" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# 7.6 — path canonicalisation: abs and rel resolve to same id
# ---------------------------------------------------------------------------


def test_abs_and_rel_spec_paths_resolve_identically(project):
    docs = project / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("x")

    plan_path = str(project / "plan.json")
    state_rel = str(project / "state-rel.json")
    state_abs = str(project / "state-abs.json")

    _write_plan(plan_path)
    init_state(plan_path, state_rel,
               spec_path="docs/spec.md",
               project_path=str(project))
    init_state(plan_path, state_abs,
               spec_path=str(project / "docs" / "spec.md"),
               project_path=str(project))

    rel_state = load_state(state_rel)
    abs_state = load_state(state_abs)
    assert rel_state.spec_lineage_id == abs_state.spec_lineage_id == "docs/spec.md"


# ---------------------------------------------------------------------------
# 7.7 — session_id survives replan; lineage survives replan and restart
# ---------------------------------------------------------------------------


def test_replan_preserves_lineage_and_session(project):
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path)
    init_state(plan_path, state_path,
               spec_path="docs/spec-v1.md",
               project_path=str(project))

    pre_state = load_state(state_path)
    pre_session = pre_state.sentinel_session_id
    pre_lineage = pre_state.spec_lineage_id

    # Simulate a replan: append two new changes via the engine helper.
    new_changes = [
        {"name": "page-checkout", "scope": "s", "complexity": "M", "phase": 1},
        {"name": "page-orders", "scope": "s", "complexity": "M", "phase": 1},
    ]
    _append_changes_to_state(state_path, new_changes)

    post_state = load_state(state_path)
    # Top-level state untouched by replan.
    assert post_state.sentinel_session_id == pre_session
    assert post_state.spec_lineage_id == pre_lineage
    # NEW changes inherit the live lineage + session id (not regenerated).
    new_added = [c for c in post_state.changes if c.name in {"page-checkout", "page-orders"}]
    assert len(new_added) == 2
    for c in new_added:
        assert c.spec_lineage_id == pre_lineage
        assert c.sentinel_session_id == pre_session


def test_restart_same_spec_keeps_lineage_changes_session(project):
    plan_path = str(project / "plan.json")
    state_path1 = str(project / "state-1.json")
    state_path2 = str(project / "state-2.json")
    _write_plan(plan_path)

    # First sentinel session.
    init_state(plan_path, state_path1,
               spec_path="docs/spec-v1.md",
               project_path=str(project))
    s1 = load_state(state_path1)

    # Second sentinel session — same spec, fresh init (operator stop+start).
    init_state(plan_path, state_path2,
               spec_path="docs/spec-v1.md",
               project_path=str(project))
    s2 = load_state(state_path2)

    assert s1.spec_lineage_id == s2.spec_lineage_id == "docs/spec-v1.md"
    # Fresh session id at every stop+start (Section 7.8).
    assert s1.sentinel_session_id != s2.sentinel_session_id


# ---------------------------------------------------------------------------
# 7.8 — session_id explicit override (replan-from-CLI use case)
# ---------------------------------------------------------------------------


def test_explicit_session_id_is_preserved(project):
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path)
    init_state(plan_path, state_path,
               spec_path="docs/spec-v1.md",
               project_path=str(project),
               sentinel_session_id="cafebabedeadbeef" * 2)
    state = load_state(state_path)
    assert state.sentinel_session_id == "cafebabedeadbeef" * 2


# ---------------------------------------------------------------------------
# Section 13.2 / AC-32 — archive entry tagging
# ---------------------------------------------------------------------------


def test_archive_entry_carries_lineage_and_session(project):
    plan_path = str(project / "plan.json")
    state_path = str(project / "state.json")
    _write_plan(plan_path)
    init_state(plan_path, state_path,
               spec_path="docs/spec-v1.md",
               project_path=str(project))

    # Mark one change as merged so it gets archived.
    state = load_state(state_path)
    state.changes[0].status = "merged"
    save_state(state, state_path)

    _archive_completed_to_jsonl(state_path)

    archive_path = os.path.join(project, "state-archive.jsonl")
    with open(archive_path) as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
    assert len(lines) == 1
    assert lines[0]["spec_lineage_id"] == "docs/spec-v1.md"
    assert lines[0]["sentinel_session_id"] == state.sentinel_session_id
    assert lines[0]["sentinel_session_started_at"] == state.sentinel_session_started_at


# ---------------------------------------------------------------------------
# Backwards-compat: legacy state files (no lineage fields) still load
# ---------------------------------------------------------------------------


def test_legacy_state_loads_without_lineage_fields(project):
    state_path = str(project / "legacy-state.json")
    with open(state_path, "w") as fh:
        json.dump(
            {
                "plan_version": 1,
                "brief_hash": "h",
                "plan_phase": "initial",
                "plan_method": "api",
                "status": "stopped",
                "created_at": "2024-01-01T00:00:00",
                "changes": [
                    {"name": "old-change", "scope": "s", "complexity": "M",
                     "phase": 1, "status": "merged"},
                ],
            },
            fh,
        )
    state = load_state(state_path)
    assert state.spec_lineage_id is None
    assert state.sentinel_session_id is None
    assert state.changes[0].spec_lineage_id is None


def test_to_dict_omits_unset_lineage_fields():
    c = Change(name="x")
    d = c.to_dict()
    # Don't pollute legacy entries with explicit nulls.
    assert "spec_lineage_id" not in d
    assert "sentinel_session_id" not in d
    assert "sentinel_session_started_at" not in d


def test_to_dict_emits_lineage_fields_when_set():
    c = Change(
        name="x",
        spec_lineage_id="docs/spec-v1.md",
        sentinel_session_id="abc",
        sentinel_session_started_at="2026-04-19T10:00:00+02:00",
    )
    d = c.to_dict()
    assert d["spec_lineage_id"] == "docs/spec-v1.md"
    assert d["sentinel_session_id"] == "abc"
    assert d["sentinel_session_started_at"] == "2026-04-19T10:00:00+02:00"
